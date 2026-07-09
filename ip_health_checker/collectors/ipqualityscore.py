from __future__ import annotations

from pathlib import Path

from .base import json_get, skipped
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    key = config.get("api_keys", {}).get("ipqualityscore")
    if not key:
        return skipped("ipqualityscore", "missing API key: api_keys.ipqualityscore or IPQS_KEY")
    url = (
        "https://ipqualityscore.com/api/json/ip/"
        f"{quote_url_value(key)}/{quote_url_value(ip)}"
        "?strictness=1&allow_public_access_points=true&fast=true"
    )
    return json_get("ipqualityscore", url, raw_dir, config)
