"""Rule-based copy quality policy."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.schemas.llm_marketing import CopyCandidate, MarketingCopy


LOW_QUALITY_PHRASES = [
    "대박",
    "역대급",
    "놓치지 마세요",
    "지금 바로",
    "최고의",
    "완벽한",
    "무조건",
    "강추",
    "혜자",
    "핫플",
    "인생맛집",
]


def sanitize_copy_text(text: str) -> str:
    cleaned = re.sub(r"[\u2600-\u27BF]+", "", text or "")
    cleaned = re.sub(r"[\"'`~*]{2,}", "", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def shorten_headline(text: str, max_chars: int = 18) -> str:
    cleaned = sanitize_copy_text(text)
    for phrase in LOW_QUALITY_PHRASES:
        cleaned = cleaned.replace(phrase, "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars].rstrip()


def normalize_cta(text: str | None) -> str:
    cleaned = sanitize_copy_text(text or "자세히 보기")
    replacements = {
        "지금 바로 확인하기": "자세히 보기",
        "지금 확인하기": "확인하기",
        "놓치지 마세요": "자세히 보기",
    }
    cleaned = replacements.get(cleaned, cleaned)
    return cleaned or "자세히 보기"


def score_copy_quality(copy: MarketingCopy | CopyCandidate | dict[str, Any]) -> dict[str, Any]:
    data = copy if isinstance(copy, dict) else copy.model_dump()
    joined = " ".join(str(data.get(key) or "") for key in ("headline", "subcopy", "cta"))
    warnings: list[str] = []
    applied_fixes: list[str] = []
    score = 1.0
    if any(phrase in joined for phrase in LOW_QUALITY_PHRASES):
        warnings.append("overused_promo_phrase_detected")
        applied_fixes.append("overused_promo_phrase_removed")
        score -= 0.15
    if "!!" in joined:
        warnings.append("excessive_exclamation_detected")
        applied_fixes.append("trimmed_exclamation_marks")
        score -= 0.1
    if len(str(data.get("headline") or "")) > 18:
        warnings.append("headline_longer_than_recommended")
        applied_fixes.append("shortened_headline")
        score -= 0.08
    return {"score": max(0.0, round(score, 2)), "warnings": warnings, "applied_fixes": applied_fixes}


def apply_copy_quality_policy(marketing_copy: MarketingCopy) -> MarketingCopy:
    quality = score_copy_quality(marketing_copy)
    metadata = dict(marketing_copy.metadata or {})
    metadata["copy_quality"] = quality
    return marketing_copy.model_copy(
        update={
            "headline": shorten_headline(marketing_copy.headline),
            "subcopy": sanitize_copy_text(marketing_copy.subcopy or "")[:35] or None,
            "cta": normalize_cta(marketing_copy.cta),
            "metadata": metadata,
        }
    )


def apply_candidate_quality_policy(candidate: CopyCandidate) -> CopyCandidate:
    copy = MarketingCopy(headline=candidate.headline, subcopy=candidate.subcopy, cta=candidate.cta)
    fixed = apply_copy_quality_policy(copy)
    metadata = {**candidate.metadata, "copy_quality": fixed.metadata.get("copy_quality", {})}
    return candidate.model_copy(
        update={"headline": fixed.headline, "subcopy": fixed.subcopy, "cta": fixed.cta, "metadata": metadata}
    )
