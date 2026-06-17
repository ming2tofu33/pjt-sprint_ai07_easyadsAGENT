from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CopySubjectAnchor:
    value: str | None
    source: str
    evidence_refs: tuple[str, ...]
    safe_for_copy: bool
    rejection_reason: str | None = None


def resolve_copy_subject_anchor(state: Mapping[str, Any] | Any) -> CopySubjectAnchor:
    payload = state if isinstance(state, Mapping) else {"context": state}
    context = _dict(payload.get("context"))
    current_brief = _dict(payload.get("current_brief"))
    validator_metadata = _dict(payload.get("validator_metadata"))
    intake_projection = _dict(validator_metadata.get("intake_understanding"))
    extra = _dict(context.get("extra"))

    rejected_item = _text(intake_projection.get("rejected_item_candidate") or extra.get("rejected_item_candidate"))
    rejection_reason = _text(intake_projection.get("rejection_reason") or extra.get("rejection_reason"))
    evidence_refs = tuple(str(item) for item in (intake_projection.get("evidence_refs") or extra.get("intake_evidence_refs") or []) if item)

    item = _text(context.get("item_or_service"))
    if item and item != rejected_item and not _unsafe_anchor(item):
        return CopySubjectAnchor(item, "item_or_service", evidence_refs, True)

    advertised_subject = _text(current_brief.get("advertised_subject") or extra.get("advertised_subject"))
    if advertised_subject and not _unsafe_anchor(advertised_subject):
        return CopySubjectAnchor(advertised_subject, "advertised_subject", evidence_refs, True, rejection_reason)

    venue_or_business = _text(extra.get("venue_type_candidate") or extra.get("business_phrase"))
    if venue_or_business and not _unsafe_anchor(venue_or_business):
        return CopySubjectAnchor(venue_or_business, "venue_or_business", evidence_refs, True, rejection_reason)

    return CopySubjectAnchor(None, "generic_safe_fallback", evidence_refs, False, rejection_reason or "missing_safe_anchor")


def _unsafe_anchor(value: str) -> bool:
    lowered = value.lower()
    if re.search(r"\b(?:create|make|poster|banner|flyer|advertisement|ad)\b", lowered):
        return True
    return any(token in value for token in ("만들어", "제작", "광고", "포스터", "배너", "전단지", "상세페이지"))


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
