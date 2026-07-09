from __future__ import annotations

from pathlib import Path

from .base import json_get, skipped
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    key = config.get("api_keys", {}).get("abuseipdb")
    if not key:
        return skipped("abuseipdb", "missing API key: api_keys.abuseipdb or ABUSEIPDB_KEY")
    url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={quote_url_value(ip)}&maxAgeInDays=90&verbose"
    return json_get("abuseipdb", url, raw_dir, config, headers={"Key": key, "Accept": "application/json"})
