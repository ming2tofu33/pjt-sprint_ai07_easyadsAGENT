"""Rule-based copy quality policy.

The v2 policy scores risky/generated copy but avoids destructive rewrites.
Custom input and generated copy keep their wording except for whitespace and
punctuation normalization.
"""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.schemas.llm_marketing import CopyCandidate, MarketingCopy


LOW_QUALITY_PHRASES = [
    "대박",
    "초특가",
    "놓치지 마세요",
    "지금 바로",
    "최고의",
    "역대급",
    "무조건",
    "강추",
    "핫딜",
    "인생맛집",
    "상품의 장점을 쉽게 확인해보세요",
    "필요한 정보를 간결하게 안내",
    "생성된 이미지만 확인하고 다운로드할 수 있어요",
]


def sanitize_copy_text(text: str) -> str:
    cleaned = re.sub(r"[\u2600-\u27BF]+", "", text or "")
    cleaned = re.sub(r"[\"'`~*]{2,}", "", cleaned)
    cleaned = re.sub(r"!{2,}", "!", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def shorten_headline(text: str, max_chars: int = 18) -> str:
    """Compatibility helper for old callers; not used for policy rewrites."""

    cleaned = sanitize_copy_text(text)
    return cleaned[:max_chars].rstrip()


def normalize_cta(text: str | None) -> str:
    """Normalize only spacing/punctuation; do not force a generic CTA."""

    cleaned = sanitize_copy_text(text or "")
    return cleaned or "문의하기"


def score_copy_quality(copy: MarketingCopy | CopyCandidate | dict[str, Any]) -> dict[str, Any]:
    data = copy if isinstance(copy, dict) else copy.model_dump()
    joined = " ".join(str(data.get(key) or "") for key in ("headline", "subcopy", "cta"))
    warnings: list[str] = []
    score = 1.0
    if any(phrase in joined for phrase in LOW_QUALITY_PHRASES):
        warnings.append("overused_or_generic_phrase_detected")
        score -= 0.15
    if "!!" in joined:
        warnings.append("excessive_exclamation_detected")
        score -= 0.1
    if len(str(data.get("headline") or "")) > 18:
        warnings.append("headline_longer_than_recommended")
        score -= 0.08
    return {"score": max(0.0, round(score, 2)), "warnings": warnings, "applied_fixes": []}


def apply_copy_quality_policy(marketing_copy: MarketingCopy) -> MarketingCopy:
    quality = score_copy_quality(marketing_copy)
    metadata = dict(marketing_copy.metadata or {})
    metadata["copy_quality"] = quality
    return marketing_copy.model_copy(
        update={
            "headline": sanitize_copy_text(marketing_copy.headline),
            "subcopy": sanitize_copy_text(marketing_copy.subcopy or "") or None,
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
