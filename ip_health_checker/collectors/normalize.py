from __future__ import annotations

from typing import Any

from ..models import Observation, SourceResult


def normalize_all(sources: dict[str, SourceResult], exit_ip: str) -> list[Observation]:
    observations = []
    for name, result in sources.items():
        if not result.data:
            continue
        obs = normalize_source(name, result.data, exit_ip)
        if obs:
            observations.append(obs)
    return observations


def normalize_source(name: str, data: dict[str, Any], exit_ip: str) -> Observation | None:
    if name == "ipinfo":
        return normalize_ipinfo(data, exit_ip)
    if name == "ipapi_is":
        return normalize_ipapi_is(data, exit_ip)
    if name == "ipregistry":
        return normalize_ipregistry(data, exit_ip)
    if name == "ipdata":
        return normalize_ipdata(data, exit_ip)
    if name == "ipqualityscore":
        return normalize_ipqs(data, exit_ip)
    if name == "abuseipdb":
        return normalize_abuseipdb(data, exit_ip)
    if name == "scamalytics":
        return Observation(source=name, ip=exit_ip, fraud_score=data.get("fraud_score"))
    return None


def normalize_ipinfo(data: dict[str, Any], exit_ip: str) -> Observation:
    loc = (data.get("loc") or "").split(",")
    latitude = _float(loc[0]) if len(loc) == 2 else None
    longitude = _float(loc[1]) if len(loc) == 2 else None
    org = data.get("org") or ""
    asn = None
    asn_name = None
    if org.startswith("AS"):
        parts = org.split(" ", 1)
        asn = parts[0].replace("AS", "")
        asn_name = parts[1] if len(parts) > 1 else None
    privacy = data.get("privacy") or {}
    return Observation(
        source="ipinfo",
        ip=data.get("ip") or exit_ip,
        country=data.get("country"),
        region=data.get("region"),
        city=data.get("city"),
        latitude=latitude,
        longitude=longitude,
        asn=asn,
        asn_name=asn_name,
        isp=asn_name,
        organization=org or None,
        is_proxy=_bool(privacy.get("proxy")),
        is_vpn=_bool(privacy.get("vpn")),
        is_tor=_bool(privacy.get("tor")),
        is_hosting=_bool(privacy.get("hosting")),
        is_datacenter=_bool(privacy.get("hosting")),
        is_anycast=_bool(data.get("anycast")),
        timezone=data.get("timezone"),
    )


def normalize_ipapi_is(data: dict[str, Any], exit_ip: str) -> Observation:
    asn = data.get("asn") or {}
    location = data.get("location") or {}
    company = data.get("company") or {}
    return Observation(
        source="ipapi.is",
        ip=data.get("ip") or exit_ip,
        country=(location.get("country_code") or "").upper() or None,
        region=location.get("state"),
        city=location.get("city"),
        latitude=_float(location.get("latitude")),
        longitude=_float(location.get("longitude")),
        asn=_asn(asn.get("asn")),
        asn_name=asn.get("org") or asn.get("descr"),
        isp=company.get("name") or asn.get("org"),
        organization=company.get("name") or asn.get("org"),
        ip_type=company.get("type") or asn.get("type"),
        is_proxy=_bool(data.get("is_proxy")),
        is_vpn=_bool(data.get("is_vpn")),
        is_tor=_bool(data.get("is_tor")),
        is_hosting=_bool(data.get("is_datacenter")),
        is_datacenter=_bool(data.get("is_datacenter")),
        is_known_abuser=_bool(data.get("is_abuser")),
        is_crawler=_bool(data.get("is_crawler")),
        is_bot=_bool(data.get("is_crawler")),
        is_bogon=_bool(data.get("is_bogon")),
        timezone=location.get("timezone"),
        currency=location.get("currency_code"),
    )


def normalize_ipregistry(data: dict[str, Any], exit_ip: str) -> Observation:
    connection = data.get("connection") or {}
    location = data.get("location") or {}
    country = location.get("country") or {}
    security = data.get("security") or {}
    company = data.get("company") or {}
    currency = data.get("currency") or {}
    time_zone = data.get("time_zone") or {}
    return Observation(
        source="ipregistry",
        ip=data.get("ip") or exit_ip,
        country=country.get("code"),
        region=(location.get("region") or {}).get("name"),
        city=location.get("city"),
        latitude=_float(location.get("latitude")),
        longitude=_float(location.get("longitude")),
        asn=_asn(connection.get("asn")),
        asn_name=connection.get("organization"),
        isp=connection.get("organization"),
        organization=company.get("name") or connection.get("organization"),
        ip_type=connection.get("type") or company.get("type"),
        is_proxy=_bool(security.get("is_proxy")),
        is_vpn=_bool(security.get("is_vpn")),
        is_tor=_bool(security.get("is_tor")) or _bool(security.get("is_tor_exit")),
        is_hosting=_bool(security.get("is_cloud_provider")),
        is_datacenter=_bool(security.get("is_cloud_provider")),
        is_known_abuser=_bool(security.get("is_abuser")),
        is_anonymous=_bool(security.get("is_anonymous")),
        is_relay=_bool(security.get("is_relay")),
        timezone=time_zone.get("id"),
        currency=currency.get("code"),
        languages=[item.get("code") for item in country.get("languages", []) if item.get("code")],
    )


def normalize_ipdata(data: dict[str, Any], exit_ip: str) -> Observation:
    asn = data.get("asn") or {}
    threat = data.get("threat") or {}
    currency = data.get("currency") or {}
    return Observation(
        source="ipdata",
        ip=data.get("ip") or exit_ip,
        country=data.get("country_code"),
        region=data.get("region"),
        city=data.get("city"),
        latitude=_float(data.get("latitude")),
        longitude=_float(data.get("longitude")),
        asn=_asn(asn.get("asn")),
        asn_name=asn.get("name"),
        isp=asn.get("name"),
        organization=asn.get("name"),
        is_proxy=_bool(threat.get("is_proxy")),
        is_vpn=_bool(threat.get("is_vpn")),
        is_tor=_bool(threat.get("is_tor")),
        is_known_abuser=_bool(threat.get("is_known_attacker")) or _bool(threat.get("is_known_abuser")),
        is_anonymous=_bool(threat.get("is_anonymous")),
        is_bot=_bool(threat.get("is_bot")),
        is_bogon=_bool(threat.get("is_bogon")),
        timezone=(data.get("time_zone") or {}).get("name"),
        currency=currency.get("code"),
        languages=[item.get("code") for item in data.get("languages", []) if item.get("code")],
    )


def normalize_ipqs(data: dict[str, Any], exit_ip: str) -> Observation:
    return Observation(
        source="ipqualityscore",
        ip=data.get("host") or data.get("ip_address") or exit_ip,
        country=data.get("country_code"),
        region=data.get("region"),
        city=data.get("city"),
        isp=data.get("ISP"),
        organization=data.get("organization"),
        is_proxy=_bool(data.get("proxy")),
        is_vpn=_bool(data.get("vpn")),
        is_tor=_bool(data.get("tor")),
        is_hosting=_bool(data.get("hosting")),
        is_datacenter=_bool(data.get("hosting")),
        is_known_abuser=_bool(data.get("recent_abuse")),
        is_bot=_bool(data.get("bot_status")),
        timezone=data.get("timezone"),
        fraud_score=_int(data.get("fraud_score")),
    )


def normalize_abuseipdb(data: dict[str, Any], exit_ip: str) -> Observation:
    item = data.get("data") or {}
    usage = item.get("usageType")
    return Observation(
        source="abuseipdb",
        ip=item.get("ipAddress") or exit_ip,
        country=item.get("countryCode"),
        isp=item.get("isp"),
        organization=item.get("domain"),
        ip_type=usage,
        is_hosting=usage == "Data Center/Web Hosting/Transit",
        is_datacenter=usage == "Data Center/Web Hosting/Transit",
        is_known_abuser=(_int(item.get("abuseConfidenceScore")) or 0) > 0,
        abuse_score=_int(item.get("abuseConfidenceScore")),
    )


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
    return None


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _asn(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value).upper().replace("AS", "").strip()
