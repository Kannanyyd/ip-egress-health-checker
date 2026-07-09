from __future__ import annotations

from typing import Any

from ..utils import curl_json, curl, first_ip, parse_cloudflare_trace


ENDPOINTS = [
    ("ipify", "https://api.ipify.org?format=json", "json_ip"),
    ("ifconfig", "https://ifconfig.co/json", "json_ip_country"),
    ("ipinfo", "https://ipinfo.io/json", "json_ip_country_org"),
    ("ipapi_co", "https://ipapi.co/json", "json_ip_country_asn"),
    ("ipwhois", "https://ipwho.is/", "json_ip_country_asn"),
    ("cloudflare_trace", "https://www.cloudflare.com/cdn-cgi/trace", "cf_trace"),
]


def check(target_ip: str, proxy: str | None, config: dict[str, Any]) -> dict[str, Any]:
    network = config.get("network", {})
    observations = []
    for name, url, parser in ENDPOINTS:
        kwargs = {
            "proxy": proxy,
            "timeout": int(network.get("timeout", 15)),
            "retries": int(network.get("retries", 1)),
            "interval": float(network.get("request_interval_seconds", 2)),
            "user_agent": network.get("user_agent", "IPHealthChecker/1.0"),
        }
        result = curl_json(url, **kwargs) if parser.startswith("json") else curl(url, **kwargs)
        observations.append(parse_observation(name, parser, result))

    ips = {item["ip"] for item in observations if item.get("ip")}
    countries = {item["country"] for item in observations if item.get("country")}
    asns = {item["asn"] for item in observations if item.get("asn")}
    exit_ip_consistent = len(ips) <= 1 and (not ips or target_ip in ips)
    country_consistent = len(countries) <= 1
    asn_consistent = len(asns) <= 1

    score = 20
    warnings = []
    if not exit_ip_consistent:
        score -= 10
        warnings.append(f"exit IP observations are inconsistent: {sorted(ips)}")
    if not country_consistent:
        score -= 5
        warnings.append(f"country observations are inconsistent: {sorted(countries)}")
    if not asn_consistent:
        score -= 3
        warnings.append(f"ASN observations are inconsistent: {sorted(asns)}")
    if proxy and target_ip not in ips:
        score -= 4
        warnings.append("proxy mode did not confirm the expected target exit IP from all endpoints")

    return {
        "exit_ip": target_ip,
        "observations": observations,
        "observed_ips": sorted(ips),
        "observed_countries": sorted(countries),
        "observed_asns": sorted(asns),
        "exit_ip_consistent": exit_ip_consistent,
        "country_consistent": country_consistent,
        "asn_consistent": asn_consistent,
        "consistency_score": max(0, score),
        "warnings": warnings,
    }


def discover_exit_ip(proxy: str | None, config: dict[str, Any]) -> dict[str, Any]:
    result = check("", proxy, config)
    counts = {}
    for item in result["observations"]:
        ip = item.get("ip")
        if ip:
            counts[ip] = counts.get(ip, 0) + 1
    selected = max(counts, key=counts.get) if counts else None
    result["exit_ip"] = selected
    return result


def from_observations(target_ip: str, observations: list[Any]) -> dict[str, Any]:
    countries = {item.country for item in observations if getattr(item, "country", None)}
    asns = {item.asn for item in observations if getattr(item, "asn", None)}
    score = 20
    warnings = []
    if len(countries) > 1:
        score -= 6 if len(countries) == 2 else 10
        warnings.append(f"country observations are inconsistent: {sorted(countries)}")
    if len(asns) > 1:
        score -= 4 if len(asns) == 2 else 8
        warnings.append(f"ASN observations are inconsistent: {sorted(asns)}")
    return {
        "exit_ip": target_ip,
        "observations": [
            {"source": item.source, "ip": item.ip, "country": item.country, "asn": item.asn, "organization": item.organization}
            for item in observations
        ],
        "observed_ips": sorted({item.ip for item in observations if item.ip}),
        "observed_countries": sorted(countries),
        "observed_asns": sorted(asns),
        "exit_ip_consistent": True,
        "country_consistent": len(countries) <= 1,
        "asn_consistent": len(asns) <= 1,
        "consistency_score": max(0, score),
        "warnings": warnings,
    }


def parse_observation(name: str, parser: str, result: dict[str, Any]) -> dict[str, Any]:
    obs = {
        "source": name,
        "ok": bool(result.get("ok")),
        "ip": None,
        "country": None,
        "asn": None,
        "organization": None,
        "elapsed_ms": result.get("elapsed_ms"),
        "error": result.get("error") or (result.get("stderr") if not result.get("ok") else None),
    }
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    if parser == "json_ip":
        obs["ip"] = data.get("ip") or first_ip(result.get("stdout", ""))
    elif parser == "json_ip_country":
        obs["ip"] = data.get("ip")
        obs["country"] = data.get("country") or data.get("country_code")
        obs["asn"] = _asn(data.get("asn"))
        obs["organization"] = data.get("org") or data.get("asn_org")
    elif parser == "json_ip_country_org":
        obs["ip"] = data.get("ip")
        obs["country"] = data.get("country")
        org = data.get("org") or ""
        if org.startswith("AS"):
            parts = org.split(" ", 1)
            obs["asn"] = _asn(parts[0])
            obs["organization"] = parts[1] if len(parts) > 1 else org
    elif parser == "json_ip_country_asn":
        obs["ip"] = data.get("ip")
        obs["country"] = data.get("country_code") or data.get("country")
        obs["asn"] = _asn(data.get("asn"))
        obs["organization"] = data.get("org") or data.get("asn_org") or data.get("connection", {}).get("org")
        if data.get("connection"):
            obs["asn"] = _asn(data["connection"].get("asn"))
    elif parser == "cf_trace":
        trace = parse_cloudflare_trace(result.get("stdout", ""))
        obs["ip"] = trace.get("ip")
        obs["country"] = trace.get("loc")
    return obs


def _asn(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).upper().replace("AS", "").strip()
    return text or None
