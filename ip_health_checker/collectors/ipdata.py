from __future__ import annotations

from pathlib import Path

from .base import json_get, skipped
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    key = config.get("api_keys", {}).get("ipdata")
    if not key:
        return skipped("ipdata", "missing API key: api_keys.ipdata or IPDATA_KEY")
    url = f"https://api.ipdata.co/{quote_url_value(ip)}?api-key={quote_url_value(key)}"
    return json_get("ipdata", url, raw_dir, config)
