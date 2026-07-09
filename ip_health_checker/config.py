from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {
        "ipinfo": "",
        "ipregistry": "",
        "ipdata": "",
        "ipqualityscore": "",
        "abuseipdb": "",
        "maxmind_db_path": "",
    },
    "network": {
        "timeout": 15,
        "retries": 1,
        "concurrency": 1,
        "request_interval_seconds": 2,
        "user_agent": "IPHealthChecker/1.0",
    },
    "dns": {
        "resolvers": [],
        "rbl_enabled": True,
    },
    "checks": {
        "basic_info": True,
        "risk_score": True,
        "rbl": True,
        "consistency": True,
        "dns_leak": True,
        "stability": True,
    },
    "stability": {
        "repeats": 3,
        "interval_seconds": 2,
        "targets": [
            "https://api.ipify.org",
            "https://www.google.com/generate_204",
            "https://www.gstatic.com/generate_204",
            "https://www.wikipedia.org",
        ],
    },
    "scoring": {
        "reputation_weight": 35,
        "consistency_weight": 20,
        "rbl_weight": 15,
        "stability_weight": 20,
        "data_quality_weight": 10,
    },
}


ENV_KEY_MAP = {
    "ipinfo": "IPINFO_TOKEN",
    "ipregistry": "IPREGISTRY_KEY",
    "ipdata": "IPDATA_KEY",
    "ipqualityscore": "IPQS_KEY",
    "abuseipdb": "ABUSEIPDB_KEY",
    "maxmind_db_path": "MAXMIND_DB_PATH",
}


def load_config(path: str | None = None) -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path:
        loaded = load_yaml_like(Path(path))
        deep_update(config, loaded)
    apply_env(config)
    return config


def quick_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    result["network"]["retries"] = 0
    result["network"]["request_interval_seconds"] = 1
    result["stability"]["repeats"] = 1
    result["checks"]["stability"] = True
    return result


def full_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    result["network"]["retries"] = max(2, int(result["network"].get("retries", 1)))
    result["stability"]["repeats"] = max(5, int(result["stability"].get("repeats", 3)))
    return result


def apply_env(config: dict[str, Any]) -> None:
    for key, env_name in ENV_KEY_MAP.items():
        if os.environ.get(env_name):
            config["api_keys"][key] = os.environ[env_name]


def deep_update(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value


def load_yaml_like(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text) or {}
        if not isinstance(loaded, dict):
            raise ValueError("config root must be a mapping")
        return loaded
    except ImportError:
        return parse_small_yaml(text)


def parse_small_yaml(text: str) -> dict[str, Any]:
    """Small YAML subset parser for config.example.yaml when PyYAML is absent."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_list_key: tuple[int, dict[str, Any], str] | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if line.startswith("- "):
            item_text = line[2:].strip()
            if pending_list_key and pending_list_key[0] < indent:
                _, owner, key = pending_list_key
                parent = owner[key]
            if not isinstance(parent, list):
                continue
            if ":" in item_text:
                key, value = item_text.split(":", 1)
                obj = {key.strip(): parse_scalar(value.strip())}
                parent.append(obj)
                stack.append((indent, obj))
            else:
                parent.append(parse_scalar(item_text))
            continue

        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            next_is_list = _next_significant_starts_with_dash(text, raw_line)
            container: Any = [] if next_is_list else {}
            parent[key] = container
            stack.append((indent, container))
            if next_is_list:
                pending_list_key = (indent, parent, key)
        else:
            parent[key] = parse_scalar(value)
            pending_list_key = None
    return root


def _next_significant_starts_with_dash(text: str, current_line: str) -> bool:
    lines = text.splitlines()
    try:
        index = lines.index(current_line)
    except ValueError:
        return False
    current_indent = len(current_line) - len(current_line.lstrip(" "))
    for line in lines[index + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        return indent > current_indent and line.strip().startswith("- ")
    return False


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "None", "~"):
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item.strip()) for item in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value
