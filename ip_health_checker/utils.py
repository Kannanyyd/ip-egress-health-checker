from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_UA = "IPHealthChecker/1.0 (+self-owned exit audit)"


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_") or "target"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_lines(path: str | Path) -> list[str]:
    lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            lines.append(value)
    return lines


def run_command(cmd: list[str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": "timeout",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }


def curl(
    url: str,
    *,
    proxy: str | None = None,
    timeout: int = 15,
    retries: int = 1,
    interval: float = 1.0,
    user_agent: str = DEFAULT_UA,
    headers: dict[str, str] | None = None,
    write_out: str | None = None,
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(max(1, retries + 1)):
        cmd = ["curl", "-L", "-sS", "--max-time", str(timeout), "-A", user_agent]
        if proxy:
            cmd += ["--proxy", proxy]
        for key, value in (headers or {}).items():
            cmd += ["-H", f"{key}: {value}"]
        if write_out:
            cmd += ["-o", "/dev/null", "-w", write_out]
        cmd.append(url)
        last = run_command(cmd, timeout + 5)
        last["url"] = url
        last["attempt"] = attempt + 1
        if last["ok"]:
            return last
        if attempt < retries:
            time.sleep(interval)
    return last or {"ok": False, "stdout": "", "stderr": "not executed", "url": url}


def curl_json(url: str, **kwargs: Any) -> dict[str, Any]:
    result = curl(url, **kwargs)
    try:
        result["json"] = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        result["json"] = None
        result["error"] = f"invalid json: {exc}"
    return result


def save_raw(raw_dir: Path, name: str, result: dict[str, Any], prefer_json: bool = False) -> str:
    ensure_dir(raw_dir)
    suffix = ".json" if prefer_json else ".txt"
    path = raw_dir / f"{slugify(name)}{suffix}"
    if prefer_json:
        payload = {
            "url": result.get("url"),
            "ok": result.get("ok"),
            "returncode": result.get("returncode"),
            "elapsed_ms": result.get("elapsed_ms"),
            "stdout": result.get("stdout"),
            "stderr": result.get("stderr"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(result.get("stdout") or "", encoding="utf-8", errors="replace")
    return str(path)


def quote_url_value(value: str) -> str:
    return quote(value, safe="")


def parse_json_output(result: dict[str, Any]) -> dict[str, Any] | None:
    if "json" in result:
        return result["json"]
    try:
        return json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError:
        return None


def first_ip(text: str) -> str | None:
    for token in re.findall(r"(?<![\w.:])(?:\d{1,3}\.){3}\d{1,3}(?![\w.:])", text):
        return token
    for token in re.findall(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:]{2,}(?![\w:])", text):
        return token
    return None


def parse_cloudflare_trace(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def has_curl() -> bool:
    return run_command(["curl", "--version"], 5)["ok"]


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def env_or_empty(name: str) -> str:
    return os.environ.get(name, "")
