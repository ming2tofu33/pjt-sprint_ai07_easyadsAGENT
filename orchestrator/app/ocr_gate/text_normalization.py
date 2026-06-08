"""OCR text normalization and similarity."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize_ocr_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.replace("\r", " ").replace("\n", " ").lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"[^\w가-힣a-z0-9]+", "", normalized, flags=re.IGNORECASE)
    return normalized


def compact_display_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", normalized).strip()


def text_similarity(left: str, right: str) -> float:
    left_norm = normalize_ocr_text(left)
    right_norm = normalize_ocr_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()

