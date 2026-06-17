"""Open-domain intake understanding contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("intake values must be strings")
    normalized = value.strip()
    return normalized or None


def _normalize_string_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("intake collections must contain strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


class IntakeUnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    business_candidate: str | None = None
    venue_type_candidate: str | None = None
    advertised_subject: str | None = None
    advertised_subject_type: str | None = None
    product_or_service_candidate: str | None = None
    campaign_intent_candidate: str | None = None
    ad_format_candidate: str | None = None

    tone_candidates: tuple[str, ...] = ()
    mood_candidates: tuple[str, ...] = ()
    target_candidates: tuple[str, ...] = ()
    time_context: tuple[str, ...] = ()
    location_context: tuple[str, ...] = ()
    contact_context: tuple[str, ...] = ()
    price_context: tuple[str, ...] = ()

    evidence_items: tuple[EvidenceItem, ...] = ()
    confidence_by_field: dict[str, float] = Field(default_factory=dict)
    ambiguity_flags: tuple[str, ...] = ()
    input_conflicts: tuple[InputConflict, ...] = ()

    extraction_mode: str
    fallback_used: StrictBool = False
    fallback_reason: str | None = None

    @field_validator(
        "business_candidate",
        "venue_type_candidate",
        "advertised_subject",
        "advertised_subject_type",
        "product_or_service_candidate",
        "campaign_intent_candidate",
        "ad_format_candidate",
        "extraction_mode",
        "fallback_reason",
        mode="before",
    )
    @classmethod
    def _normalize_optional_strings(cls, value: Any) -> str | None:
        return _normalize_optional_text(value)

    @field_validator(
        "tone_candidates",
        "mood_candidates",
        "target_candidates",
        "time_context",
        "location_context",
        "contact_context",
        "price_context",
        "ambiguity_flags",
        mode="before",
    )
    @classmethod
    def _normalize_string_collections(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value)

    @field_validator("confidence_by_field", mode="before")
    @classmethod
    def _normalize_confidence_map(cls, value: Any) -> dict[str, float]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("confidence_by_field must be a mapping")
        normalized: dict[str, float] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise ValueError("confidence_by_field keys must be strings")
            key = raw_key.strip()
            if not key:
                continue
            confidence = float(raw_value)
            if confidence < 0.0 or confidence > 1.0:
                raise ValueError("confidence_by_field values must be between 0 and 1")
            normalized[key] = confidence
        return normalized

    @model_validator(mode="after")
    def _validate_evidence_contract(self) -> "IntakeUnderstandingResult":
        evidence_keys = {item.key for item in self.evidence_items}
        required_keys = {
            "business_candidate": self.business_candidate,
            "venue_type_candidate": self.venue_type_candidate,
            "advertised_subject": self.advertised_subject,
            "advertised_subject_type": self.advertised_subject_type,
            "product_or_service_candidate": self.product_or_service_candidate,
            "campaign_intent_candidate": self.campaign_intent_candidate,
            "ad_format_candidate": self.ad_format_candidate,
        }
        for key, value in required_keys.items():
            if value and key not in evidence_keys:
                raise ValueError(f"{key} requires evidence")
        collection_keys = {
            "tone_candidates": self.tone_candidates,
            "mood_candidates": self.mood_candidates,
            "target_candidates": self.target_candidates,
            "time_context": self.time_context,
            "location_context": self.location_context,
            "contact_context": self.contact_context,
            "price_context": self.price_context,
        }
        for key, values in collection_keys.items():
            if values and key not in evidence_keys:
                raise ValueError(f"{key} requires evidence")
        return self
