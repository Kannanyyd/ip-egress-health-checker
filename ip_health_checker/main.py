from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path
from typing import Any

from .checks import consistency, dns_leak, rbl, stability
from .collectors import (
    collect_abuseipdb,
    collect_ipapi_is,
    collect_ipdata,
    collect_ipinfo,
    collect_ipqualityscore,
    collect_ipregistry,
    collect_scamalytics,
)
from .collectors.normalize import normalize_all
from .config import full_config, load_config, quick_config
from .models import SourceResult, Target, TargetReport
from .report import manual_review_links, write_reports
from .scoring import score_report
from .utils import ensure_dir, has_curl, read_lines, slugify


COLLECTORS = [
    collect_ipinfo,
    collect_ipapi_is,
    collect_ipregistry,
    collect_ipdata,
    collect_ipqualityscore,
    collect_abuseipdb,
    collect_scamalytics,
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Self-owned VPS/proxy exit IP health checker.")
    parser.add_argument("--ips", help="file with one IP per line")
    parser.add_argument("--proxies", help="file with one proxy URL per line")
    parser.add_argument("--config", help="config YAML file")
    parser.add_argument("--output", default="reports", help="output directory")
    parser.add_argument("--quick", action="store_true", help="run lower-repeat, lower-retry checks")
    parser.add_argument("--full", action="store_true", help="run fuller low-frequency checks")
    parser.add_argument("--format", default="md,csv,json", help="comma-separated output formats: md,csv,json")
    parser.add_argument("--dry-run", action="store_true", help="load inputs/config and print planned targets only")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.ips and not args.proxies:
        print("Provide --ips or --proxies.", file=sys.stderr)
        return 2
    if not has_curl():
        print("curl is required because it provides consistent proxy support, including socks5/socks5h.", file=sys.stderr)
        return 2

    config = load_config(args.config)
    if args.quick:
        config = quick_config(config)
    if args.full:
        config = full_config(config)

    targets = load_targets(args)
    if not targets:
        print("No valid targets found in input files.", file=sys.stderr)
        return 2
    if args.dry_run:
        for target in targets:
            print(f"{target.mode}\t{target.name}\t{target.ip or target.proxy}")
        return 0

    output_dir = Path(args.output)
    ensure_dir(output_dir / "raw")
    ensure_dir(output_dir / "logs")

    reports = []
    for target in targets:
        report = audit_target(target, output_dir, config)
        reports.append(report)
        print(f"{target.name}\t{report.exit_ip}\t{report.scores['total_score']}\t{report.scores['recommendation']}")

    formats = {item.strip() for item in args.format.split(",") if item.strip()}
    write_reports(reports, output_dir, formats)
    return 0


def load_targets(args: argparse.Namespace) -> list[Target]:
    targets = []
    if args.ips:
        for idx, ip in enumerate(read_lines(args.ips), 1):
            targets.append(Target(name=f"ip-{idx}-{slugify(ip)}", mode="ip", ip=validate_ip(ip)))
    if args.proxies:
        for idx, proxy in enumerate(read_lines(args.proxies), 1):
            targets.append(Target(name=f"proxy-{idx}", mode="proxy", proxy=proxy))
    return targets


def validate_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as exc:
        raise SystemExit(f"invalid IP in input: {value}") from exc


def audit_target(target: Target, output_dir: Path, config: dict[str, Any]) -> TargetReport:
    raw_dir = ensure_dir(output_dir / "raw" / slugify(target.name))
    warnings = []
    proxy_consistency = None
    exit_ip = target.ip
    if target.mode == "proxy":
        proxy_consistency = consistency.discover_exit_ip(target.proxy, config)
        exit_ip = proxy_consistency.get("exit_ip")
        if not exit_ip:
            exit_ip = "0.0.0.0"
            warnings.append("failed to discover proxy exit IP")

    sources = collect_sources(exit_ip, raw_dir, config)
    observations = normalize_all(sources, exit_ip)
    if proxy_consistency:
        consistency_result = consistency.check(exit_ip, target.proxy, config)
    else:
        consistency_result = consistency.from_observations(exit_ip, observations)

    exit_country = first_country(observations, consistency_result)
    dns_result = dns_leak.check(exit_country, config) if config.get("checks", {}).get("dns_leak", True) else {"skipped": True}
    rbl_result = rbl.check(exit_ip, config) if config.get("checks", {}).get("rbl", True) else {"skipped": True}
    stability_result = (
        stability.check(target.proxy, config) if config.get("checks", {}).get("stability", True) else {"skipped": True}
    )

    scores = score_report(observations, sources, consistency_result, dns_result, rbl_result, stability_result, config)
    warnings.extend(collect_warnings(sources, consistency_result, dns_result, rbl_result))
    return TargetReport(
        target=target,
        exit_ip=exit_ip,
        observations=observations,
        sources=sources,
        consistency=consistency_result,
        dns_leak=dns_result,
        rbl=rbl_result,
        stability=stability_result,
        scores=scores,
        manual_review_links=manual_review_links(exit_ip),
        warnings=warnings,
    )


def collect_sources(ip: str, raw_dir: Path, config: dict[str, Any]) -> dict[str, SourceResult]:
    results = {}
    for collector in COLLECTORS:
        try:
            result = collector(ip, raw_dir, config)
            results[result.source] = result
        except Exception as exc:
            source = getattr(collector, "__module__", "collector").split(".")[-1]
            results[source] = SourceResult(source=source, ok=False, error=str(exc))
    return results


def first_country(observations: list[Any], consistency_result: dict[str, Any]) -> str | None:
    for obs in observations:
        if obs.country:
            return obs.country
    countries = consistency_result.get("observed_countries") or []
    return countries[0] if countries else None


def collect_warnings(*items: Any) -> list[str]:
    warnings = []
    for item in items:
        if isinstance(item, dict):
            warnings.extend(item.get("warnings", []))
            if item.get("skipped") and item.get("reason"):
                warnings.append(item["reason"])
        elif isinstance(item, dict):
            warnings.extend(item.get("warnings", []))
    for source in items[0].values() if items and isinstance(items[0], dict) else []:
        if isinstance(source, SourceResult):
            warnings.extend(source.warnings)
            if source.error and not source.skipped:
                warnings.append(f"{source.source}: {source.error}")
    return list(dict.fromkeys(str(item) for item in warnings if item))


if __name__ == "__main__":
    raise SystemExit(main())
