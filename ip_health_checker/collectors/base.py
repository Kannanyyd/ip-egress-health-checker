from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceResult
from ..utils import curl_json, save_raw


def source_context(config: dict[str, Any]) -> dict[str, Any]:
    network = config.get("network", {})
    return {
        "timeout": int(network.get("timeout", 15)),
        "retries": int(network.get("retries", 1)),
        "interval": float(network.get("request_interval_seconds", 2)),
        "user_agent": network.get("user_agent", "IPHealthChecker/1.0"),
    }


def json_get(
    source: str,
    url: str,
    raw_dir: Path,
    config: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> SourceResult:
    ctx = source_context(config)
    result = curl_json(url, headers=headers, **ctx)
    raw_file = save_raw(raw_dir, source, result, prefer_json=True)
    data = result.get("json") if isinstance(result.get("json"), dict) else None
    ok = bool(result.get("ok") and data is not None)
    error = None
    if not ok:
        error = result.get("error") or result.get("stderr") or "request failed"
    return SourceResult(source=source, ok=ok, data=data, error=error, raw_file=raw_file)


def skipped(source: str, reason: str) -> SourceResult:
    return SourceResult(source=source, ok=False, skipped=True, error=reason)
