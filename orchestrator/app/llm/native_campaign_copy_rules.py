"""Shared deterministic rules for native campaign copy planning."""

from __future__ import annotations

import re


NEW_MENU_KO = "\uc2e0\uba54\ub274"
NEW_PRODUCT_KO = "\uc2e0\uc81c\ud488"
NEW_RELEASE_KO = "\uc0c8\ub85c \ucd9c\uc2dc"
RELEASE_KO = "\ucd9c\uc2dc"
INTRODUCE_KO = "\uc18c\uac1c"
PROMOTE_KO = "\ud64d\ubcf4"
AD_KO = "\uad11\uace0"

CAMPAIGN_MODIFIER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bnew\s+menu\b",
        r"\bnew\s+product\b",
        r"\bnew\s+release\b",
        NEW_MENU_KO,
        NEW_PRODUCT_KO,
        NEW_RELEASE_KO,
        r"\ucd9c\uc2dc\s*\uc608\uc815",
        RELEASE_KO,
    )
]

GENERIC_REQUEST_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        INTRODUCE_KO + r"\s*(?:\ud558\uace0\s*\uc2f6\uc5b4|\ud574\uc918|\ud574\s*\uc8fc\uc138\uc694)?",
        PROMOTE_KO + r"\s*(?:\ud558\uace0\s*\ud574|\ud558\uace0\s*\uc2f6\uc5b4|\ud574\uc918|\ud574\s*\uc8fc\uc138\uc694)?",
        AD_KO,
        r"\bi\s+want\s+to\s+promote\b",
        r"\bpromote\b",
        r"\badvertis(?:e|ing|ement)\b",
        r"\bintroduce\b",
        r"\bcreate\s+an\s+ad\b",
        r"\bmake\s+an\s+advertisement\b",
    )
]

GENERIC_LAUNCH_COPY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bintroducing\s+(?:our\s+)?new\b",
        r"\bnow\s+available\b",
        r"\bmeet\s+(?:our\s+)?new\b",
        r"\bnew\s+(?:menu|product)\b",
        r"\uc0c8\ub86d\uac8c\s*\uc120\ubcf4\uc774\ub294",
        r"\uc0c8\ub85c\uc6b4\s*\uba54\ub274",
        r"\uc0c8\ub85c\s*\ub9cc\ub098\ub294",
        r"\uc9c0\uae08\s*\uacf5\uac1c",
        r"\ucd9c\uc2dc\s*\uae30\ub150",
        NEW_MENU_KO,
        NEW_PRODUCT_KO,
    )
]


def detect_campaign_status(text: str | None) -> str | None:
    value = text or ""
    lowered = value.lower()
    if NEW_MENU_KO in value or re.search(r"\bnew\s+menu\b", lowered):
        return "new_menu"
    if NEW_PRODUCT_KO in value or re.search(r"\bnew\s+product\b", lowered):
        return "new_product"
    if NEW_RELEASE_KO in value or re.search(r"\bnew\s+release\b", lowered):
        return "new_product"
    if RELEASE_KO in value:
        return "new_product"
    if "\uc2dc\uc98c" in value or "seasonal" in lowered:
        return "seasonal"
    return None


def contains_campaign_modifier(text: str | None) -> bool:
    return any(pattern.search(text or "") for pattern in CAMPAIGN_MODIFIER_PATTERNS)


def strip_campaign_modifiers(text: str | None) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    for pattern in CAMPAIGN_MODIFIER_PATTERNS:
        value = pattern.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,.-")
    return value or None


def strip_generic_request_language(text: str | None) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    for pattern in GENERIC_REQUEST_PATTERNS:
        value = pattern.sub(" ", value)
    value = re.sub(r"\b(?:for|as|with)\b\s*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" ,.-")
    return value or None


def clean_product_identity(text: str | None) -> str | None:
    value = strip_generic_request_language(text)
    value = strip_campaign_modifiers(value)
    if value:
        value = re.split(r"\s*(?:\ub97c|\uc744)\s+", value, maxsplit=1)[0].strip()
        value = re.sub(r"\s*(?:\ub97c|\uc744|\uc774|\uac00|\uc73c\ub85c|\ub85c)\s*$", "", value).strip()
    return value or None


def contains_generic_launch_copy(text: str | None) -> bool:
    return any(pattern.search(text or "") for pattern in GENERIC_LAUNCH_COPY_PATTERNS)


def is_generic_request_only(text: str | None) -> bool:
    stripped = strip_generic_request_language(text)
    return not stripped
