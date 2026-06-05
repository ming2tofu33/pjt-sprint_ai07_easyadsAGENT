"""Sanitization helpers for chat thread payloads."""

from __future__ import annotations

from typing import Any

_SENSITIVE_KEYS = {
    "apikey",
    "openaiapikey",
    "hftoken",
    "huggingfacetoken",
    "token",
    "authorization",
    "password",
    "secret",
    "servicerolekey",
    "databaseurl",
    "chainofthought",
    "rawllmresponse",
    "rawprompt",
    "systemprompt",
}


def sanitize_chat_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_chat_payload(item)
            for key, item in value.items()
            if _normalize_sensitive_key(key) not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [sanitize_chat_payload(item) for item in value[:50]]
    if isinstance(value, str) and len(value) > 2000:
        return f"{value[:1997]}..."
    return value


def _normalize_sensitive_key(value: object) -> str:
    return "".join(char for char in str(value).lower() if char.isalnum())
