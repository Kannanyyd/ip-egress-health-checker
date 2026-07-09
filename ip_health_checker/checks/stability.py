from __future__ import annotations

import statistics
import time
from typing import Any

from ..utils import curl


def check(proxy: str | None, config: dict[str, Any]) -> dict[str, Any]:
    network = config.get("network", {})
    stability = config.get("stability", {})
    repeats = int(stability.get("repeats", 3))
    interval = float(stability.get("interval_seconds", network.get("request_interval_seconds", 2)))
    targets = stability.get("targets") or []
    results = []
    for target in targets:
        for attempt in range(repeats):
            result = measure(target, proxy, config)
            result["attempt"] = attempt + 1
            results.append(result)
            if interval > 0 and not (target == targets[-1] and attempt == repeats - 1):
                time.sleep(interval)

    total = len(results)
    ok_results = [item for item in results if item["ok"]]
    latencies = [item["total_ms"] for item in ok_results if item.get("total_ms") is not None]
    success_rate = (len(ok_results) / total) if total else 0.0
    timeout_count = sum(1 for item in results if item.get("failure_reason") == "timeout")
    score = stability_score(success_rate, latencies, timeout_count)
    return {
        "targets": targets,
        "results": results,
        "success_rate": round(success_rate, 4),
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_latency_ms": round(percentile(latencies, 50), 2) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 95), 2) if latencies else None,
        "timeout_count": timeout_count,
        "failure_reasons": failure_reasons(results),
        "network_stability_score": score,
    }


def measure(url: str, proxy: str | None, config: dict[str, Any]) -> dict[str, Any]:
    network = config.get("network", {})
    write_out = "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}"
    result = curl(
        url,
        proxy=proxy,
        timeout=int(network.get("timeout", 15)),
        retries=0,
        user_agent=network.get("user_agent", "IPHealthChecker/1.0"),
        write_out=write_out,
    )
    parts = (result.get("stdout") or "").strip().split()
    status = None
    connect_ms = None
    first_byte_ms = None
    total_ms = None
    if len(parts) == 4:
        status = safe_int(parts[0])
        connect_ms = safe_seconds_ms(parts[1])
        first_byte_ms = safe_seconds_ms(parts[2])
        total_ms = safe_seconds_ms(parts[3])
    ok = bool(result.get("ok") and status and 200 <= status < 400)
    reason = None
    if not ok:
        stderr = result.get("stderr") or ""
        if "timed out" in stderr.lower() or stderr == "timeout":
            reason = "timeout"
        elif status:
            reason = f"http_{status}"
        else:
            reason = stderr[-120:] or "request_failed"
    return {
        "url": url,
        "ok": ok,
        "http_status": status,
        "connect_ms": connect_ms,
        "first_byte_ms": first_byte_ms,
        "total_ms": total_ms,
        "failure_reason": reason,
    }


def stability_score(success_rate: float, latencies: list[float], timeout_count: int) -> int:
    score = 20
    if success_rate < 0.9:
        score -= int((0.9 - success_rate) * 40)
    if timeout_count:
        score -= min(8, timeout_count * 2)
    if latencies:
        p95 = percentile(latencies, 95)
        if p95 > 5000:
            score -= 8
        elif p95 > 3000:
            score -= 5
        elif p95 > 1500:
            score -= 2
    else:
        score = 0
    return max(0, min(20, score))


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * (pct / 100)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def failure_reasons(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {}
    for item in results:
        reason = item.get("failure_reason")
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def safe_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def safe_seconds_ms(value: str) -> float | None:
    try:
        return float(value) * 1000
    except ValueError:
        return None
