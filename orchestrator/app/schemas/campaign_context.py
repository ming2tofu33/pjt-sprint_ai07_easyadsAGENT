"""Campaign input context contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("campaign context values must be strings")
    normalized = value.strip()
    return normalized or None


def normalize_string_list(values: Iterable[str] | None) -> tuple[str, ...]:
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
            raise ValueError("campaign context list values must be strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


class CampaignContext(BaseModel):
    """Evidence-backed campaign input context.

    This model contains campaign intent supplied or normalized upstream.
    It does not contain copy, typography, visual strategy, preset, template,
    or provider decisions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_intent: str | None = None
    campaign_status: str | None = None
    promotion_goal: str | None = None
    desired_positioning: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("campaign_intent", "campaign_status", "promotion_goal", mode="before")
    @classmethod
    def normalize_optional_field(cls, value: Any) -> str | None:
        return normalize_optional_text(value)

    @field_validator("desired_positioning", "evidence_refs", mode="before")
    @classmethod
    def normalize_list_field(cls, value: Any) -> tuple[str, ...]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def require_evidence_for_campaign_claims(self) -> "CampaignContext":
        has_campaign_claims = bool(
            self.campaign_intent
            or self.campaign_status
            or self.promotion_goal
            or self.desired_positioning
        )
        if has_campaign_claims and not self.evidence_refs:
            raise ValueError("campaign context claims require evidence_refs")
        return self
