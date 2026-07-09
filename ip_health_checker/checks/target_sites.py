from __future__ import annotations


def check(*_args, **_kwargs) -> dict:
    return {
        "ok": False,
        "skipped": True,
        "reason": "Target-site probing is intentionally disabled in the safe default health-check profile.",
    }
