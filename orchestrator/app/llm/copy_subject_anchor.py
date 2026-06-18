from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Mapping


@dataclass(frozen=True)
class CopySubjectAnchor:
    value: str | None
    source: str
    evidence_refs: tuple[str, ...]
    safe_for_copy: bool
    rejection_reason: str | None = None
    validation_status: str = "accepted"


def resolve_copy_subject_anchor(state: Mapping[str, Any] | Any) -> CopySubjectAnchor:
    payload = _payload(state)
    context = _dict(payload.get("context"))
    current_brief = _dict(payload.get("current_brief"))
    validator_metadata = _dict(payload.get("validator_metadata"))
    intake_projection = _dict(validator_metadata.get("intake_understanding"))
    extra = _dict(context.get("extra"))

    source_text = _text(payload.get("user_input") or intake_projection.get("source_text") or extra.get("source_text"))
    rejected_item = _text(intake_projection.get("rejected_item_candidate") or extra.get("rejected_item_candidate"))
    rejection_reason = _text(intake_projection.get("rejection_reason") or extra.get("rejection_reason"))
    evidence_by_source = _evidence_by_source(intake_projection, extra)
    campaign_intent = _text(current_brief.get("campaign_intent") or payload.get("campaign_intent") or extra.get("campaign_intent"))

    item = _text(context.get("item_or_service"))
    advertised_subject = _text(current_brief.get("advertised_subject") or extra.get("advertised_subject"))
    venue_or_business = _text(extra.get("venue_type_candidate") or extra.get("business_phrase"))

    if (
        item
        and item != rejected_item
        and not _business_subject_conflict(item, campaign_intent, advertised_subject, venue_or_business)
        and not _unsafe_anchor(item, source_text=source_text)
    ):
        return CopySubjectAnchor(item, "item_or_service", evidence_by_source("item_or_service"), True)

    if advertised_subject and advertised_subject != rejected_item and not _unsafe_anchor(advertised_subject, source_text=source_text):
        return CopySubjectAnchor(advertised_subject, "advertised_subject", evidence_by_source("advertised_subject"), True, rejection_reason)

    if venue_or_business and venue_or_business != rejected_item and not _unsafe_anchor(venue_or_business, source_text=source_text):
        return CopySubjectAnchor(venue_or_business, "venue_or_business", evidence_by_source("venue_or_business"), True, rejection_reason)

    return CopySubjectAnchor(
        None,
        "generic_safe_fallback",
        evidence_by_source("generic_safe_fallback"),
        False,
        rejection_reason or "missing_safe_anchor",
        "rejected",
    )


def _payload(state: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(state, Mapping):
        if "context" in state or "current_brief" in state or "validator_metadata" in state:
            payload = dict(state)
            payload["context"] = _dict(payload.get("context"))
            return payload
        return {"context": dict(state)}
    return {"context": state}


def _business_subject_conflict(
    item: str,
    campaign_intent: str | None,
    advertised_subject: str | None,
    venue_or_business: str | None,
) -> bool:
    if campaign_intent not in {
        "store_opening",
        "brand_awareness",
        "business_introduction",
        "local_business_promotion",
        "organization_promotion",
        "student_recruitment",
    }:
        return False
    item_norm = _normalize_subject(item)
    for subject in (advertised_subject, venue_or_business):
        subject_norm = _normalize_subject(subject)
        if not subject_norm:
            continue
        if item_norm == subject_norm or subject_norm in item_norm or item_norm in subject_norm:
            return True
        item_tokens = set(item_norm.split())
        subject_tokens = set(subject_norm.split())
        if len(item_tokens & subject_tokens) >= 2:
            return True
    return False


def _normalize_subject(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(value or "").casefold())).strip()


def _unsafe_anchor(value: str, *, source_text: str | None = None) -> bool:
    lowered = value.lower()
    if len(value) > 60:
        return True
    if source_text:
        source = source_text.strip()
        if value == source:
            return True
        if len(value) >= 30 and source and (len(value) / max(len(source), 1)) >= 0.45:
            if SequenceMatcher(None, value, source).ratio() >= 0.55:
                return True
    if re.search(r"\b(?:create|make|poster|banner|flyer|advertisement|ad|target|tone|location|audience)\b", lowered):
        return True
    return any(
        token in value
        for token in (
            "\ub9cc\ub4e4",
            "\uc81c\uc791",
            "\uad11\uace0",
            "\ud3ec\uc2a4\ud130",
            "\ubc30\ub108",
            "\uc804\ub2e8\uc9c0",
            "\uc0c1\uc138\ud398\uc774\uc9c0",
            "\ud0c0\uae43",
            "\ubd84\uc704\uae30",
            "\uc704\uce58",
            "\uc694\uccad",
        )
    )


def _evidence_refs(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value if item)


def _evidence_by_source(intake_projection: dict[str, Any], extra: dict[str, Any]):
    source_maps = (
        intake_projection.get("field_evidence_refs"),
        intake_projection.get("evidence_refs_by_field"),
        extra.get("field_evidence_refs"),
        extra.get("copy_subject_evidence_refs"),
    )
    fallback = _evidence_refs(intake_projection.get("evidence_refs") or extra.get("intake_evidence_refs"))

    def resolve(source: str) -> tuple[str, ...]:
        for source_map in source_maps:
            if not isinstance(source_map, dict):
                continue
            refs = _evidence_refs(source_map.get(source))
            if refs:
                return refs
        return fallback

    return resolve


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
