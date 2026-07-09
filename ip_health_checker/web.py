from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import full_config, load_config, quick_config
from .main import audit_target
from .models import Target, TargetReport
from .report import primary_observation, sorted_reports, write_reports
from .utils import curl_json, ensure_dir, has_curl, slugify


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = PROJECT_ROOT / "web_static"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Web UI for IP egress health checks.")
    parser.add_argument("--host", default="127.0.0.1", help="host to bind")
    parser.add_argument("--port", default=8765, type=int, help="port to bind")
    parser.add_argument("--config", help="config YAML file")
    parser.add_argument("--output", default="reports", help="base output directory")
    parser.add_argument("--quick", action="store_true", help="use quick low-frequency check settings")
    parser.add_argument("--full", action="store_true", help="use full low-frequency check settings")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    if args.quick:
        config = quick_config(config)
    if args.full:
        config = full_config(config)

    handler = make_handler(config, Path(args.output))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"IP egress health checker Web UI: {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


def make_handler(config: dict[str, Any], output_base: Path) -> type[BaseHTTPRequestHandler]:
    class WebHandler(BaseHTTPRequestHandler):
        server_version = "IPHealthCheckerWeb/1.0"

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            parsed = urlparse(self.path)
            path = "/" if parsed.path == "/" else parsed.path
            if path == "/api/current":
                self.send_json(detect_current_exit(config))
                return
            if path == "/":
                self.send_static(STATIC_ROOT / "index.html")
                return
            static_path = safe_static_path(path)
            if static_path and static_path.exists() and static_path.is_file():
                self.send_static(static_path)
                return
            self.send_json({"ok": False, "error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
            parsed = urlparse(self.path)
            if parsed.path != "/api/check":
                self.send_json({"ok": False, "error": "not found"}, status=404)
                return
            try:
                payload = self.read_json_body()
                response = run_check_request(payload, output_base, config)
                self.send_json(response)
            except Exception as exc:  # keep one failed request from killing the server
                self.send_json({"ok": False, "error": str(exc)}, status=500)

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

        def read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON body: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError("JSON body must be an object")
            return value

        def send_static(self, path: Path) -> None:
            if not path.exists() or not path.is_file():
                self.send_json({"ok": False, "error": "not found"}, status=404)
                return
            content = path.read_bytes()
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

    return WebHandler


def detect_current_exit(config: dict[str, Any]) -> dict[str, Any]:
    if not has_curl():
        return {"ok": False, "error": "curl is required to detect current exit IP"}
    network = config.get("network", {})
    common = {
        "timeout": int(network.get("timeout", 15)),
        "retries": int(network.get("retries", 1)),
        "interval": float(network.get("request_interval_seconds", 1)),
        "user_agent": str(network.get("user_agent", "IPHealthChecker/1.0")),
    }
    for source, url in (
        ("api.ipify.org", "https://api.ipify.org?format=json"),
        ("ifconfig.co", "https://ifconfig.co/json"),
    ):
        result = curl_json(url, **common)
        data = result.get("json") or {}
        ip = data.get("ip") or data.get("ip_addr")
        if result.get("ok") and ip:
            return {"ok": True, "ip": str(ip), "source": source}
    return {"ok": False, "error": "failed to detect current exit IP"}


def safe_static_path(path: str) -> Path | None:
    relative = unquote(path.lstrip("/"))
    if not relative or ".." in Path(relative).parts:
        return None
    candidate = (STATIC_ROOT / relative).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return None
    return candidate


def run_check_request(payload: dict[str, Any], output_base: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not has_curl():
        return {"ok": False, "error": "curl is required for health checks"}

    raw_ips = payload.get("ips") or []
    if isinstance(raw_ips, str):
        raw_ips = [line.strip() for line in raw_ips.splitlines()]
    if not isinstance(raw_ips, list):
        return {"ok": False, "error": "ips must be a list"}

    targets, input_errors = parse_ip_targets(raw_ips)
    if not targets:
        return {"ok": False, "error": "no valid IP addresses", "input_errors": input_errors}

    run_id = dt.datetime.now(dt.timezone.utc).strftime("web-%Y%m%dT%H%M%S%fZ")
    output_dir = ensure_dir(output_base / run_id)
    ensure_dir(output_dir / "raw")
    ensure_dir(output_dir / "logs")

    reports: list[TargetReport] = []
    run_errors: list[dict[str, str]] = []
    for target in targets:
        try:
            reports.append(audit_target(target, output_dir, config))
        except Exception as exc:
            run_errors.append({"target": target.name, "ip": target.ip or "", "error": str(exc)})

    write_reports(reports, output_dir, {"md", "csv", "json"})
    ordered = sorted_reports(reports)
    return {
        "ok": True,
        "run_id": run_id,
        "output_dir": str(output_dir),
        "input_errors": input_errors,
        "run_errors": run_errors,
        "reports": [web_report(item, rank) for rank, item in enumerate(ordered, 1)],
    }


def parse_ip_targets(values: list[Any]) -> tuple[list[Target], list[dict[str, str]]]:
    targets: list[Target] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        try:
            ip = str(ipaddress.ip_address(value))
        except ValueError:
            errors.append({"input": value, "error": "invalid IP address"})
            continue
        if ip in seen:
            continue
        seen.add(ip)
        targets.append(Target(name=f"ip-{len(targets) + 1}-{slugify(ip)}", mode="ip", ip=ip))
    return targets, errors


def web_report(item: TargetReport, rank: int) -> dict[str, Any]:
    primary = primary_observation(item)
    dimensions = item.scores.get("dimensions", {})
    profile = profile_summary(item)
    return {
        "rank": rank,
        "name": item.target.name,
        "ip": item.exit_ip,
        "score": item.scores.get("total_score"),
        "recommendation": item.scores.get("recommendation"),
        "ip_type": item.scores.get("ip_type"),
        "profile": profile,
        "country": primary.get("country"),
        "city": primary.get("city"),
        "asn": primary.get("asn"),
        "isp": primary.get("isp"),
        "organization": primary.get("organization"),
        "dimensions": dimensions,
        "rbl": {
            "listed_count": item.rbl.get("rbl_listed_count"),
            "listed_names": item.rbl.get("rbl_listed_names") or [],
            "risk_level": item.rbl.get("rbl_risk_level"),
            "blocked_names": item.rbl.get("rbl_query_blocked_names") or [],
        },
        "consistency": item.consistency,
        "dns_leak": item.dns_leak,
        "stability": {
            "success_rate": item.stability.get("success_rate"),
            "avg_latency_ms": item.stability.get("avg_latency_ms"),
            "p50_latency_ms": item.stability.get("p50_latency_ms"),
            "p95_latency_ms": item.stability.get("p95_latency_ms"),
            "timeout_count": item.stability.get("timeout_count"),
        },
        "main_reasons": item.scores.get("main_reasons", []),
        "source_conflicts": item.scores.get("source_conflicts", {}),
        "warnings": item.warnings,
        "manual_review_links": item.manual_review_links,
    }


def profile_summary(item: TargetReport) -> dict[str, Any]:
    observations = item.observations
    values = [str(obs.ip_type or "").lower() for obs in observations]
    ok_sources = [name for name, result in item.sources.items() if getattr(result, "ok", False)]
    source_count = len(ok_sources)
    conflicts = item.scores.get("source_conflicts", {}) if item.scores else {}
    score_reasons = [str(reason).lower() for reason in item.scores.get("main_reasons", [])] if item.scores else []
    country_consistent = item.consistency.get("country_consistent")
    asn_consistent = item.consistency.get("asn_consistent")
    listed_count = int(item.rbl.get("rbl_listed_count") or 0)
    flags = {
        "tor": any(obs.is_tor for obs in observations),
        "proxy": any(obs.is_proxy for obs in observations),
        "vpn": any(obs.is_vpn for obs in observations),
        "anonymous": any(obs.is_anonymous for obs in observations),
        "relay": any(obs.is_relay for obs in observations),
        "abuser": any(obs.is_known_abuser for obs in observations),
        "bot": any(obs.is_bot or obs.is_crawler for obs in observations),
        "hosting": any(obs.is_hosting or obs.is_datacenter for obs in observations)
        or any("hosting" in value or "data center" in value or "datacenter" in value or "transit" in value for value in values),
        "residential": any("residential" in value or "household" in value or "consumer" in value for value in values),
        "isp": any("isp" in value or "fixed line" in value or "broadband" in value or "cable/dsl" in value for value in values),
        "business": any(
            "business" in value or "organization" in value or "commercial" in value or "corporate" in value
            for value in values
        ),
        "mobile": any("mobile" in value for value in values),
        "education": any("education" in value or "university" in value for value in values),
        "government": any("government" in value for value in values),
        "anycast": any(obs.is_anycast for obs in observations),
        "bogon": any(obs.is_bogon for obs in observations),
        "rbl": listed_count > 0,
        "country_conflict": (country_consistent is False) or ("country" in conflicts),
        "asn_conflict": (asn_consistent is False) or ("asn" in conflicts),
        "city_conflict": "city" in conflicts,
        "org_conflict": "organization" in conflicts,
        "dns_mismatch": bool(item.dns_leak.get("dns_leak_suspected")),
        "infra_risk": any(
            "owner mismatch" in reason
            or "upstream asn" in reason
            or "hosting/reseller" in reason
            or "business ip is less proven" in reason
            for reason in score_reasons
        ),
    }

    tags: list[dict[str, str]] = []
    primary = "未知类型"
    primary_tone = "neutral"

    if flags["tor"]:
        primary = "Tor出口"
        primary_tone = "bad"
    elif flags["proxy"]:
        primary = "代理IP"
        primary_tone = "bad"
    elif flags["vpn"]:
        primary = "VPN出口"
        primary_tone = "bad"
    elif flags["residential"]:
        primary = "住宅IP"
        primary_tone = "good"
    elif flags["isp"]:
        primary = "家宽/ISP"
        primary_tone = "good"
    elif flags["mobile"]:
        primary = "移动网络"
        primary_tone = "good"
    elif flags["hosting"]:
        primary = "机房IP"
        primary_tone = "warn"
    elif flags["business"]:
        primary = "商业宽带"
        primary_tone = "neutral"

    privacy_or_special = any(flags[name] for name in ("tor", "proxy", "vpn", "anonymous", "relay", "bogon"))
    if privacy_or_special:
        native_label = "非原生/隐私出口"
        native_tone = "bad"
    elif flags["country_conflict"] or flags["asn_conflict"] or flags["city_conflict"]:
        native_label = "归属异常"
        native_tone = "warn"
    elif flags["org_conflict"] or flags["infra_risk"]:
        native_label = "原生待复核"
        native_tone = "warn"
    elif source_count >= 2 and not flags["rbl"]:
        native_label = "原生IP倾向"
        native_tone = "good"
    else:
        native_label = "原生待复核"
        native_tone = "neutral"

    if flags["tor"] or flags["bogon"]:
        risk_label = "高风险"
        risk_tone = "bad"
    elif flags["proxy"] or flags["vpn"]:
        risk_label = "代理/VPN 风险"
        risk_tone = "bad"
    elif flags["rbl"] or flags["abuser"] or flags["bot"]:
        risk_label = "有风险命中"
        risk_tone = "bad"
    elif flags["city_conflict"] or flags["org_conflict"] or flags["infra_risk"]:
        risk_label = "机房/转租风险"
        risk_tone = "warn"
    elif flags["dns_mismatch"] or flags["country_conflict"] or flags["asn_conflict"]:
        risk_label = "归属需复核"
        risk_tone = "warn"
    elif flags["hosting"]:
        risk_label = "机房常见风控"
        risk_tone = "warn"
    else:
        risk_label = "未见明显风险"
        risk_tone = "good"

    tags.append(tag(native_label, native_tone))
    tags.append(tag(primary, primary_tone))

    if flags["education"]:
        tags.append(tag("教育网", "neutral"))
    if flags["government"]:
        tags.append(tag("政府网络", "neutral"))
    if flags["anycast"]:
        tags.append(tag("任播 Anycast", "neutral"))
    if flags["anonymous"]:
        tags.append(tag("匿名网络", "bad"))
    if flags["relay"]:
        tags.append(tag("中继出口", "warn"))
    if flags["abuser"]:
        tags.append(tag("滥用记录", "bad"))
    if flags["bot"]:
        tags.append(tag("Bot/爬虫", "bad"))
    if flags["bogon"]:
        tags.append(tag("保留/异常段", "bad"))
    if flags["rbl"]:
        tags.append(tag("RBL 命中", "bad"))
    else:
        tags.append(tag("RBL 未命中", "good"))
    if flags["dns_mismatch"]:
        tags.append(tag("DNS 国家不一致", "warn"))
    if flags["country_conflict"]:
        tags.append(tag("国家归属冲突", "warn"))
    if flags["asn_conflict"]:
        tags.append(tag("ASN 冲突", "warn"))
    if flags["city_conflict"]:
        tags.append(tag("城市库冲突", "warn"))
    if flags["org_conflict"]:
        tags.append(tag("主体不一致", "warn"))
    if flags["infra_risk"]:
        tags.append(tag("转租/上游风险", "warn"))
    if (
        source_count >= 2
        and not flags["country_conflict"]
        and not flags["asn_conflict"]
        and not flags["city_conflict"]
        and not flags["org_conflict"]
        and not flags["infra_risk"]
    ):
        tags.append(tag("多源归属一致", "good"))
    if source_count <= 1:
        tags.append(tag("数据源不足", "warn"))

    if not tags:
        tags.append(tag("需人工复核", "neutral"))

    evidence = []
    evidence.append("国家归属冲突" if flags["country_conflict"] else "国家归属一致")
    evidence.append("ASN 冲突" if flags["asn_conflict"] else "ASN 一致")
    if flags["city_conflict"]:
        evidence.append("城市/地理库不一致")
    if flags["org_conflict"]:
        evidence.append("组织/主体归属不一致")
    if flags["infra_risk"]:
        evidence.append("存在转租或上游 ASN 痕迹")
    evidence.append(f"RBL 命中 {listed_count} 个" if listed_count else "RBL 未命中")
    evidence.append(f"{source_count} 个公开源可用" if source_count else "公开源不足")
    if flags["dns_mismatch"]:
        evidence.append("DNS 出口国家疑似不一致")

    summary = f"{primary}，{native_label}，{risk_label}。{evidence[0]}，{evidence[1]}。"

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item_tag in tags:
        if item_tag["label"] not in seen:
            deduped.append(item_tag)
            seen.add(item_tag["label"])

    return {
        "primary": primary,
        "primary_tone": primary_tone,
        "native": native_label,
        "native_tone": native_tone,
        "risk": risk_label,
        "risk_tone": risk_tone,
        "summary": summary,
        "tags": deduped,
        "evidence": evidence,
        "source_count": source_count,
        "source_names": ok_sources,
    }


def tag(label: str, tone: str) -> dict[str, str]:
    return {"label": label, "tone": tone}


if __name__ == "__main__":
    raise SystemExit(main())
