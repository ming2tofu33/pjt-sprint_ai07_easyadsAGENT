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


# Internal reasoning/format labels that some LLM outputs leak into the visible
# copy fields (e.g. "AI\uCD94\uCC9C=\uC2E0\uBA54\uB274 \uCE58\uD0A8 / Sub: \uC774\uBCA4\uD2B8 \uBD84\uC704\uAE30\uB85C...") instead of
# writing clean copy. The schema already separates headline/subcopy/rationale,
# so any such label inside a visible field is leakage.
_META_LABEL_TOKENS = (
    r"(?:ai\s*\uCD94\uCC9C|\uCD94\uCC9C|head(?:line)?|sub(?:copy)?|\uC11C\uBE0C\uCE74\uD53C|\uC11C\uBE0C|\uD5E4\uB4DC\uB77C\uC778|\uCE74\uD53C|rationale|reason|\uC774\uC720|\uBA54\uBAA8)"
)
_LEADING_LABEL_RE = re.compile(rf"^\s*{_META_LABEL_TOKENS}\s*[:=]\s*", re.IGNORECASE)
_INLINE_LABEL_RE = re.compile(rf"\s*[/|]\s*{_META_LABEL_TOKENS}\s*[:=].*$", re.IGNORECASE)


def strip_meta_labels(text: str) -> str:
    """Strip leaked reasoning/format labels from user-visible copy.

    Defensive second safety net behind the prompt fix: removes a trailing
    "/ Sub: ..." style labeled segment and any leading "AI\uCD94\uCC9C=" / "Sub:" label.
    Only recognized label tokens followed by ':' or '=' are removed, so normal
    copy (e.g. "24/7", "\uCD94\uCC9C \uBA54\uB274") is left intact.
    """
    cleaned = _INLINE_LABEL_RE.sub("", text or "")
    while True:
        stripped = _LEADING_LABEL_RE.sub("", cleaned)
        if stripped == cleaned:
            break
        cleaned = stripped
    return cleaned.strip()


def sanitize_copy_text(text: str) -> str:
    cleaned = strip_meta_labels(text or "")
    cleaned = re.sub(r"[\u2600-\u27BF]+", "", cleaned)
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
