from __future__ import annotations

import re
from pathlib import Path

from ..models import SourceResult
from ..utils import curl, quote_url_value, save_raw
from .base import source_context


def collect(ip: str, raw_dir: Path, config: dict) -> SourceResult:
    ctx = source_context(config)
    result = curl(f"https://scamalytics.com/ip/{quote_url_value(ip)}", **ctx)
    raw_file = save_raw(raw_dir, "scamalytics", result, prefer_json=False)
    body = result.get("stdout") or ""
    warnings = []
    if "Cloudflare" in body and ("challenge" in body.lower() or "blocked" in body.lower()):
        warnings.append("Scamalytics returned Cloudflare/challenge page; no bypass attempted")
        return SourceResult(
            source="scamalytics",
            ok=False,
            data={"blocked_or_challenged": True},
            error="blocked_or_challenged",
            warnings=warnings,
            raw_file=raw_file,
        )
    score = None
    for pattern in (
        r"Fraud Score:\s*</[^>]+>\s*<[^>]+>\s*(\d{1,3})",
        r"Fraud Score[^0-9]{1,80}(\d{1,3})",
        r"score[^0-9]{1,50}(\d{1,3})",
    ):
        match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if match:
            score = int(match.group(1))
            break
    data = {"fraud_score": score, "blocked_or_challenged": False}
    return SourceResult(source="scamalytics", ok=result.get("ok", False), data=data, raw_file=raw_file)
