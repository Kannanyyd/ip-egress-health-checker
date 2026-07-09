from __future__ import annotations

from pathlib import Path

from .base import json_get, skipped
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    key = config.get("api_keys", {}).get("ipregistry")
    if not key:
        return skipped("ipregistry", "missing API key: api_keys.ipregistry or IPREGISTRY_KEY")
    url = f"https://api.ipregistry.co/{quote_url_value(ip)}?key={quote_url_value(key)}&hostname=true"
    return json_get("ipregistry", url, raw_dir, config)
