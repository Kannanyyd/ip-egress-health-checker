from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from ..utils import curl_json


def check(exit_country: str | None, config: dict[str, Any]) -> dict[str, Any]:
    resolvers = system_resolvers()
    configured = config.get("dns", {}).get("resolvers") or []
    all_resolvers = []
    for item in resolvers:
        all_resolvers.append({"source": "system", "ip": item})
    for item in configured:
        all_resolvers.append({"source": "configured", "ip": item})

    enriched = []
    for resolver in all_resolvers:
        ip = resolver["ip"]
        if is_private_or_special(ip):
            enriched.append({**resolver, "country": None, "asn": None, "note": "private_or_special"})
            continue
        geo = curl_json(f"https://ipwho.is/{ip}", timeout=10, retries=0)
        data = geo.get("json") if isinstance(geo.get("json"), dict) else {}
        connection = data.get("connection") or {}
        enriched.append(
            {
                **resolver,
                "country": data.get("country_code"),
                "asn": connection.get("asn"),
                "organization": connection.get("org") or connection.get("isp"),
                "ok": geo.get("ok", False),
            }
        )

    countries = {item.get("country") for item in enriched if item.get("country")}
    suspected = False
    if exit_country and countries and any(country != exit_country for country in countries):
        suspected = True
    score = 10 if not suspected else 5
    return {
        "system_resolvers": resolvers,
        "resolver_observations": enriched,
        "dns_resolver_country": sorted(countries),
        "dns_leak_suspected": suspected,
        "dns_leak_score": score,
        "note": "This is a basic resolver-country heuristic, not a browser DNS leak test.",
    }


def system_resolvers() -> list[str]:
    path = Path("/etc/resolv.conf")
    if not path.exists():
        return []
    values = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("nameserver "):
            value = line.split()[1]
            values.append(value)
    return values


def is_private_or_special(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return True
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
