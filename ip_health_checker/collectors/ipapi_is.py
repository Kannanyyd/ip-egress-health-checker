from __future__ import annotations

from pathlib import Path

from .base import json_get
from ..utils import quote_url_value


def collect(ip: str, raw_dir: Path, config: dict) -> object:
    return json_get("ipapi_is", f"https://api.ipapi.is/?q={quote_url_value(ip)}", raw_dir, config)
