"""Business environment context contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain


def normalize_open_label(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("open label must be a string")
    normalized = value.strip()
    return normalized or None


def normalize_tag_list(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("tag and evidence lists must contain strings only")
        normalized_value = value.strip()
        if not normalized_value or normalized_value in seen:
            continue
        normalized.append(normalized_value)
        seen.add(normalized_value)
    return normalized


class BusinessEnvironmentContext(BaseModel):
    """Evidence-backed business and venue context.

    This model describes the business environment only. It must not contain
    product identity, preparation methods, creative copy, or visual strategy
    identifiers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    broad_domain: CanonicalBusinessDomain

    venue_type: str | None = None
    service_model: str | None = None

    business_tags: list[str] = Field(default_factory=list)
    environment_tags: list[str] = Field(default_factory=list)

    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("venue_type", "service_model", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return normalize_open_label(value)

    @field_validator("business_tags", "environment_tags", "evidence_refs", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return normalize_tag_list([value])
        return normalize_tag_list(value)

    @model_validator(mode="after")
    def require_evidence_for_specific_environment(self) -> "BusinessEnvironmentContext":
        has_specific_environment = bool(
            self.venue_type
            or self.service_model
            or self.business_tags
            or self.environment_tags
        )
        if has_specific_environment and not self.evidence_refs:
            raise ValueError("specific business environment fields require evidence_refs")
        return self
