from __future__ import annotations

from pathlib import Path

from .base import json_get
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    token = config.get("api_keys", {}).get("ipinfo")
    url = f"https://ipinfo.io/{quote_url_value(ip)}/json"
    if token:
        url = f"{url}?token={quote_url_value(token)}"
    return json_get("ipinfo", url, raw_dir, config)
