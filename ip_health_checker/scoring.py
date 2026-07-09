from __future__ import annotations

import re
from typing import Any

from .models import Observation


def score_report(
    observations: list[Observation],
    sources: dict[str, Any],
    consistency: dict[str, Any],
    dns_leak: dict[str, Any],
    rbl: dict[str, Any],
    stability: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    conflicts = source_conflicts(observations)
    reputation = score_reputation(observations, sources)
    consistency_detail = score_consistency(consistency, dns_leak, conflicts)
    consistency_score = consistency_detail["score"]
    rbl_score = int(rbl.get("rbl_score", 0))
    stability_score = int(stability.get("network_stability_score", 0))
    data_quality = score_data_quality(sources)
    total = reputation["score"] + consistency_score + rbl_score + stability_score + data_quality["score"]
    total = max(0, min(100, total))
    reasons = []
    reasons.extend(reputation["reasons"])
    reasons.extend(consistency.get("warnings", []))
    reasons.extend(consistency_detail["reasons"])
    if rbl.get("rbl_listed_names"):
        reasons.append("RBL listed: " + ", ".join(rbl["rbl_listed_names"]))
    if stability_score < 15:
        reasons.append("network stability score is low")
    reasons.extend(data_quality["reasons"])

    return {
        "total_score": total,
        "recommendation": recommendation(total),
        "dimensions": {
            "reputation": {"score": reputation["score"], "max_score": 35, "reasons": reputation["reasons"]},
            "consistency": {
                "score": consistency_score,
                "max_score": 20,
                "reasons": consistency.get("warnings", []) + consistency_detail["reasons"],
            },
            "rbl": {
                "score": rbl_score,
                "max_score": 15,
                "reasons": rbl.get("rbl_listed_names", []) or [rbl.get("reason", "clean")],
            },
            "stability": {
                "score": stability_score,
                "max_score": 20,
                "reasons": list(stability.get("failure_reasons", {}).keys()),
            },
            "data_quality": {"score": data_quality["score"], "max_score": 10, "reasons": data_quality["reasons"]},
        },
        "main_reasons": reasons[:8],
        "ip_type": infer_ip_type(observations),
        "source_conflicts": conflicts,
    }


def score_reputation(observations: list[Observation], sources: dict[str, Any] | None = None) -> dict[str, Any]:
    score = 35
    reasons = []
    markers = {
        "tor": any(item.is_tor for item in observations),
        "proxy": any(item.is_proxy for item in observations),
        "vpn": any(item.is_vpn for item in observations),
        "known_abuser": any(item.is_known_abuser for item in observations),
        "bot_or_crawler": any(item.is_bot or item.is_crawler for item in observations),
        "datacenter": any(item.is_datacenter or item.is_hosting for item in observations),
        "bogon": any(item.is_bogon for item in observations),
    }
    if markers["tor"]:
        score -= 30
        reasons.append("one or more sources mark Tor")
    if markers["proxy"]:
        score -= 18
        reasons.append("one or more sources mark proxy")
    if markers["vpn"]:
        score -= 14
        reasons.append("one or more sources mark VPN")
    if markers["known_abuser"]:
        score -= 16
        reasons.append("one or more sources mark known abuser/recent abuse")
    if markers["bot_or_crawler"]:
        score -= 10
        reasons.append("one or more sources mark bot/crawler")
    if markers["datacenter"]:
        score -= 10
        reasons.append("one or more sources mark hosting/datacenter")
    if markers["bogon"]:
        score -= 35
        reasons.append("one or more sources mark bogon")

    for item in observations:
        if item.fraud_score is not None:
            if item.fraud_score > 80:
                score -= 16
                reasons.append(f"{item.source} fraud_score={item.fraud_score}")
            elif item.fraud_score >= 50:
                score -= 8
                reasons.append(f"{item.source} fraud_score={item.fraud_score}")
        if item.abuse_score is not None:
            if item.abuse_score >= 75:
                score -= 18
                reasons.append(f"{item.source} abuse_score={item.abuse_score}")
            elif item.abuse_score >= 25:
                score -= 8
                reasons.append(f"{item.source} abuse_score={item.abuse_score}")

    infra = score_infrastructure_risk(observations, sources or {})
    score -= infra["penalty"]
    reasons.extend(infra["reasons"])

    positive_types = [str(item.ip_type).lower() for item in observations if item.ip_type]
    if any(value in ("isp", "fixed line isp") or "residential" in value or "broadband" in value for value in positive_types):
        score = min(35, score + 3)
    return {"score": max(0, min(35, score)), "reasons": reasons}


def score_consistency(consistency: dict[str, Any], dns_leak: dict[str, Any], conflicts: dict[str, list[str]]) -> dict[str, Any]:
    score = int(consistency.get("consistency_score", 0))
    reasons = []
    if dns_leak.get("dns_leak_suspected"):
        score -= 4
        reasons.append("DNS resolver country differs from exit country")
    if conflicts.get("city"):
        score -= 5
        reasons.append("city/geolocation differs across sources")
    if conflicts.get("organization"):
        score -= 4
        reasons.append("organization attribution differs across sources")
    return {"score": max(0, score), "reasons": reasons}


def score_infrastructure_risk(observations: list[Observation], sources: dict[str, Any]) -> dict[str, Any]:
    penalty = 0
    reasons = []
    ipapi_data = _source_data(sources, "ipapi_is")
    company = ipapi_data.get("company") or {}
    asn = ipapi_data.get("asn") or {}
    abuse = ipapi_data.get("abuse") or {}
    location = ipapi_data.get("location") or {}

    company_name = str(company.get("name") or "").strip()
    asn_org = str(asn.get("org") or asn.get("descr") or "").strip()
    company_type = str(company.get("type") or "").lower()
    asn_type = str(asn.get("type") or "").lower()
    netname = str(company.get("netname") or "").strip()
    network = str(company.get("network") or "").strip()
    domain = str(company.get("domain") or "").strip()
    mismatch = bool(company_name and asn_org and orgs_differ(company_name, asn_org))

    if mismatch:
        penalty += 4
        reasons.append(f"company/asn owner mismatch: {company_name} over {asn_org}")

    if mismatch and company_type in {"business", "organization"} and asn_type in {"isp", "hosting"}:
        penalty += 3
        reasons.append(f"business allocation rides upstream ASN: company={company_name}, asn={asn_org}")

    infra_text = " ".join([company_name, domain, netname, network, asn_org]).lower()
    infra_keywords = (
        "host",
        "hosting",
        "qechost",
        "colo",
        "colocation",
        "cloud",
        "server",
        "vps",
        "dedicated",
        "transit",
        "lease",
        "datacenter",
        "data center",
    )
    matched = [word for word in infra_keywords if word in infra_text]
    if matched:
        penalty += 4
        label = netname or company_name or asn_org
        reasons.append(f"hosting/reseller naming signal: {label}")

    has_strong_positive_type = any(
        _contains_any(item.ip_type, ("residential", "fixed line", "broadband")) for item in observations if item.ip_type
    )
    has_business_type = company_type == "business" or any(str(item.ip_type or "").lower() == "business" for item in observations)
    if has_business_type and not has_strong_positive_type:
        penalty += 2
        reasons.append("business IP is less proven than residential/ISP for long-term browser exit")

    abuse_address = str(abuse.get("address") or "").upper()
    location_country = str(location.get("country_code") or "").upper()
    if location_country and abuse_address and not abuse_address.endswith(location_country):
        penalty += 1
        reasons.append("abuse contact country differs from IP geolocation country")

    return {"penalty": min(14, penalty), "reasons": reasons}


def score_data_quality(sources: dict[str, Any]) -> dict[str, Any]:
    required = ["ipinfo", "ipapi_is", "scamalytics"]
    optional_keyed = ["ipregistry", "ipdata", "ipqualityscore", "abuseipdb"]
    ok_count = sum(1 for item in sources.values() if getattr(item, "ok", False))
    skipped_count = sum(1 for item in sources.values() if getattr(item, "skipped", False))
    failed_count = sum(1 for item in sources.values() if not getattr(item, "ok", False) and not getattr(item, "skipped", False))
    score = min(10, 4 + ok_count)
    if failed_count:
        score -= min(3, failed_count)
    reasons = []
    missing_required = [name for name in required if name in sources and not sources[name].ok]
    if missing_required:
        reasons.append("missing or failed public sources: " + ", ".join(missing_required))
    skipped_keyed = [name for name in optional_keyed if name in sources and sources[name].skipped]
    if skipped_keyed:
        reasons.append("optional keyed sources skipped: " + ", ".join(skipped_keyed))
    if skipped_count >= 3:
        score -= 1
    return {"score": max(0, min(10, score)), "reasons": reasons}


def recommendation(total: int) -> str:
    if total >= 85:
        return "适合作为主出口继续观察"
    if total >= 70:
        return "可用，但建议观察"
    if total >= 55:
        return "只建议备用"
    if total >= 40:
        return "不建议长期使用"
    return "高风险，不建议使用"


def infer_ip_type(observations: list[Observation]) -> str:
    values = [str(item.ip_type).lower() for item in observations if item.ip_type]
    if any("mobile" in item for item in values):
        return "Mobile"
    if any("education" in item for item in values):
        return "Education"
    if any("government" in item for item in values):
        return "Government"
    if any("hosting" in item or "data center" in item or "datacenter" in item for item in values):
        return "Datacenter/Hosting"
    if any("isp" in item or "fixed line" in item for item in values):
        return "ISP"
    if any("business" in item or "organization" in item for item in values):
        return "Business"
    if any(item.is_datacenter or item.is_hosting for item in observations):
        return "Datacenter/Hosting"
    return "Unknown"


def source_conflicts(observations: list[Observation]) -> dict[str, list[str]]:
    conflicts = {}
    for field in ("country", "asn", "city", "organization"):
        values = {}
        for item in observations:
            value = getattr(item, field)
            if value:
                key = conflict_key(field, str(value))
                values.setdefault(key, {"values": set(), "sources": []})
                values[key]["values"].add(str(value))
                values[key]["sources"].append(item.source)
        if len(values) > 1:
            conflicts[field] = [
                f"{' / '.join(sorted(item['values']))}: {', '.join(item['sources'])}" for item in values.values()
            ]
    return conflicts


GENERIC_ORG_TOKENS = {
    "as",
    "asn",
    "llc",
    "ltd",
    "limited",
    "inc",
    "corp",
    "corporation",
    "company",
    "co",
    "communications",
    "communication",
    "telecom",
    "telecommunications",
    "network",
    "networks",
    "internet",
    "technologies",
    "technology",
    "services",
    "service",
    "group",
    "global",
    "holdings",
}


def _source_data(sources: dict[str, Any], name: str) -> dict[str, Any]:
    result = sources.get(name)
    data = getattr(result, "data", None)
    return data if isinstance(data, dict) else {}


def _contains_any(value: str | None, needles: tuple[str, ...]) -> bool:
    text = str(value or "").lower()
    return any(needle in text for needle in needles)


def conflict_key(field: str, value: str) -> str:
    if field == "asn":
        return value.upper().replace("AS", "").strip()
    if field == "organization":
        tokens = org_tokens(value)
        if tokens:
            return "|".join(sorted(tokens))
    return value.strip().lower()


def orgs_differ(left: str, right: str) -> bool:
    left_tokens = org_tokens(left)
    right_tokens = org_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return left_tokens.isdisjoint(right_tokens)


def org_tokens(value: str) -> set[str]:
    text = re.sub(r"\bAS\d+\b", " ", value.upper())
    tokens = {item.lower() for item in re.findall(r"[A-Z0-9]+", text)}
    return {item for item in tokens if len(item) > 2 and item not in GENERIC_ORG_TOKENS}
