from __future__ import annotations

import ipaddress
import socket
import uuid
from typing import Any

from ..utils import curl_json
from ..utils import run_command


RBL_ZONES = [
    {"name": "Spamhaus ZEN", "zone": "zen.spamhaus.org", "severity": "critical"},
    {"name": "SpamCop", "zone": "bl.spamcop.net", "severity": "high"},
    {"name": "SORBS", "zone": "dnsbl.sorbs.net", "severity": "medium"},
    {"name": "Barracuda", "zone": "b.barracudacentral.org", "severity": "high"},
    {"name": "CBL AbuseAt", "zone": "cbl.abuseat.org", "severity": "critical"},
    {"name": "UCEPROTECT L1", "zone": "dnsbl-1.uceprotect.net", "severity": "medium"},
    {"name": "UCEPROTECT L2", "zone": "dnsbl-2.uceprotect.net", "severity": "high"},
    {"name": "UCEPROTECT L3", "zone": "dnsbl-3.uceprotect.net", "severity": "high"},
    {"name": "PSBL", "zone": "psbl.surriel.com", "severity": "medium"},
    {"name": "HostKarma", "zone": "hostkarma.junkemailfilter.com", "severity": "medium"},
    {"name": "SpamEatingMonkey", "zone": "bl.spameatingmonkey.net", "severity": "medium"},
    {"name": "Truncate GBUDB", "zone": "truncate.gbudb.net", "severity": "medium"},
]


def check(ip: str, config: dict[str, Any]) -> dict[str, Any]:
    if not config.get("dns", {}).get("rbl_enabled", True):
        return skipped("disabled by config")
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return skipped("invalid IP")
    if ip_obj.version != 4:
        return skipped("DNSBL check currently supports IPv4 only")

    resolvers = list(config.get("dns", {}).get("resolvers") or [None])
    for fallback in ("doh:cloudflare", "doh:google"):
        if fallback not in resolvers:
            resolvers.append(fallback)
    resolver_results = []
    checks = []
    usable_resolver = None
    for resolver in resolvers:
        synthetic = synthetic_dns_answers(resolver)
        resolver_results.append({"resolver": resolver or "system", "synthetic_answers": synthetic})
        if not synthetic and usable_resolver is None:
            usable_resolver = resolver

    if len(resolver_results) > 0 and usable_resolver is None:
        return {
            **skipped("all configured/system resolvers return synthetic answers for nonexistent domains"),
            "resolver_results": resolver_results,
        }

    reversed_ip = ".".join(reversed(ip.split(".")))
    for zone in RBL_ZONES:
        query = f"{reversed_ip}.{zone['zone']}"
        answers = resolve_a(query, usable_resolver)
        status = "clean"
        if answers:
            if any(answer.startswith("127.255.255.") for answer in answers):
                status = "query_blocked"
            elif any(answer.startswith("127.") for answer in answers):
                status = "listed"
            else:
                status = "unexpected_answer"
        checks.append({**zone, "query": query, "status": status, "answers": answers})

    listed = [item for item in checks if item["status"] == "listed"]
    query_blocked = [item for item in checks if item["status"] == "query_blocked"]
    score = rbl_score(listed)
    risk = "low"
    if score < 5:
        risk = "critical"
    elif score < 9:
        risk = "high"
    elif score < 13:
        risk = "medium"

    return {
        "ok": True,
        "resolver_used": usable_resolver or "system",
        "resolver_results": resolver_results,
        "rbl_total_checked": len(checks),
        "rbl_listed_count": len(listed),
        "rbl_listed_names": [item["name"] for item in listed],
        "rbl_query_blocked_names": [item["name"] for item in query_blocked],
        "rbl_score": score,
        "rbl_risk_level": risk,
        "checks": checks,
        "note": "DNSBL/RBL mainly reflects mail reputation; it is not a direct browser-risk verdict.",
    }


def skipped(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "skipped": True,
        "reason": reason,
        "rbl_total_checked": 0,
        "rbl_listed_count": 0,
        "rbl_listed_names": [],
        "rbl_query_blocked_names": [],
        "rbl_score": 0,
        "rbl_risk_level": "unknown",
        "checks": [],
    }


def rbl_score(listed: list[dict[str, Any]]) -> int:
    score = 15
    for item in listed:
        if item["severity"] == "critical":
            score -= 8
        elif item["severity"] == "high":
            score -= 5
        else:
            score -= 3
    return max(0, score)


def synthetic_dns_answers(resolver: str | None) -> list[str]:
    query = f"iphealth-nxdomain-{uuid.uuid4().hex}.invalid"
    return resolve_a(query, resolver)


def resolve_a(query: str, resolver: str | None) -> list[str]:
    if resolver and resolver.startswith("doh:"):
        return resolve_a_doh(query, resolver)
    dig = run_dig(query, resolver)
    if dig is not None:
        return dig
    try:
        socket.setdefaulttimeout(4)
        _, _, answers = socket.gethostbyname_ex(query)
        return answers
    except socket.gaierror:
        return []
    except Exception:
        return []


def run_dig(query: str, resolver: str | None) -> list[str] | None:
    cmd = ["dig", "+short", "+time=4", "+tries=1"]
    if resolver:
        cmd.append(f"@{resolver}")
    cmd += [query, "A"]
    result = run_command(cmd, timeout=7)
    if result["returncode"] is None:
        return None
    if result["returncode"] != 0 and not result.get("stdout"):
        return None
    answers = []
    for line in result.get("stdout", "").splitlines():
        value = line.strip()
        try:
            ipaddress.ip_address(value)
            answers.append(value)
        except ValueError:
            continue
    return answers


def resolve_a_doh(query: str, resolver: str) -> list[str]:
    if resolver == "doh:google":
        url = f"https://dns.google/resolve?name={query}&type=A"
        result = curl_json(url, timeout=8, retries=0)
    else:
        url = f"https://cloudflare-dns.com/dns-query?name={query}&type=A"
        result = curl_json(url, timeout=8, retries=0, headers={"accept": "application/dns-json"})
    data = result.get("json") if isinstance(result.get("json"), dict) else {}
    answers = []
    for item in data.get("Answer", []) or []:
        value = item.get("data")
        if not value:
            continue
        try:
            ipaddress.ip_address(value)
            answers.append(value)
        except ValueError:
            continue
    return answers
