from __future__ import annotations


def check(*_args, **_kwargs) -> dict:
    return {
        "ok": False,
        "skipped": True,
        "reason": "Unlock checks are not part of the default self-owned exit health audit.",
    }
