from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path


ALLOWED_IPV4 = {
    "0.0.0.0",
    "127.0.0.1",
    "1.1.1.1",
    "8.8.8.8",
    "9.9.9.9",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".pyc",
}

IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LOCAL_PATH_RE = re.compile(r"(?<![\w/])/(?:Users|home)/[^\s'\"`<>)]*")
SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|token|secret|password|passwd|private[_-]?key)\b"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{12,}"
)


def tracked_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
    names = result.stdout.decode("utf-8").split("\0")
    return [Path(name) for name in names if name]


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in IPV4_RE.finditer(line):
            value = match.group(0)
            if is_allowed_ipv4(value):
                continue
            findings.append(f"{path}:{lineno}: public/example IPv4 literal is not allowed: {value}")
        if EMAIL_RE.search(line):
            findings.append(f"{path}:{lineno}: email address literal is not allowed")
        if LOCAL_PATH_RE.search(line):
            findings.append(f"{path}:{lineno}: local absolute user path is not allowed")
        if SECRET_RE.search(line):
            findings.append(f"{path}:{lineno}: possible secret literal is not allowed")
    return findings


def is_allowed_ipv4(value: str) -> bool:
    if value in ALLOWED_IPV4:
        return True
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_unspecified


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if path.exists() and is_text_file(path):
            findings.extend(scan_file(path))
    if findings:
        print("Privacy scan failed. Replace real values with placeholders before committing.", file=sys.stderr)
        for item in findings:
            print(item, file=sys.stderr)
        return 1
    print("Privacy scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
