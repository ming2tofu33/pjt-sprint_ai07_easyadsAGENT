"""Env-file loader for guarded actual runners."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def load_env_file(path: str | Path | None) -> dict[str, Any]:
    """Load KEY=VALUE lines without overwriting existing process env."""
    if not path:
        return {"env_file": None, "env_file_found": False, "loaded_keys": [], "skipped_existing_keys": []}

    env_path = Path(path)
    if not env_path.exists():
        return {"env_file": str(env_path), "env_file_found": False, "loaded_keys": [], "skipped_existing_keys": []}

    loaded: list[str] = []
    skipped: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            skipped.append(key)
            continue
        os.environ[key] = value
        loaded.append(key)

    return {"env_file": str(env_path), "env_file_found": True, "loaded_keys": loaded, "skipped_existing_keys": skipped}


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].strip()
    if "=" not in text:
        return None
    key, value = text.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = _strip_inline_comment(value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char
        elif char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value
