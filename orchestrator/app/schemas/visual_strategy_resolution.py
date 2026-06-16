"""Deterministic visual strategy resolution contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orchestrator.app.schemas.visual_strategy import normalize_required_label, normalize_string_set


def _strict_non_negative_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return float(value)


def _strict_unit_float(value: Any, field_name: str) -> float:
    normalized = _strict_non_negative_float(value, field_name)
    if normalized > 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return normalized


class VisualStrategyRuntimeContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available_provider_capabilities: frozenset[str] = Field(default_factory=frozenset)
    campaign_roles: frozenset[str] = Field(default_factory=frozenset)
    placement: str | None = None

    @field_validator("available_provider_capabilities", "campaign_roles", mode="before")
    @classmethod
    def normalize_sets(cls, value: Any) -> frozenset[str]:
        return normalize_string_set(value)

    @field_validator("placement", mode="before")
    @classmethod
    def normalize_placement(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_required_label(value)


class VisualStrategyScoringPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    evidence_alignment_weight: float
    product_relevance_weight: float
    campaign_fit_weight: float
    format_fit_weight: float
    environment_fit_weight: float
    reference_fit_weight: float
    unsupported_inference_penalty_weight: float
    fallback_penalty_weight: float
    unrestricted_axis_score: float
    fallback_tier_step: float

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: Any) -> str:
        return normalize_required_label(value)

    @field_validator(
        "evidence_alignment_weight",
        "product_relevance_weight",
        "campaign_fit_weight",
        "format_fit_weight",
        "environment_fit_weight",
        "reference_fit_weight",
        "unsupported_inference_penalty_weight",
        "fallback_penalty_weight",
        mode="before",
    )
    @classmethod
    def validate_weight(cls, value: Any) -> float:
        return _strict_non_negative_float(value, "weight")

    @field_validator("unrestricted_axis_score", "fallback_tier_step", mode="before")
    @classmethod
    def validate_unit_value(cls, value: Any) -> float:
        return _strict_unit_float(value, "policy value")

    @model_validator(mode="after")
    def require_positive_weight(self) -> "VisualStrategyScoringPolicy":
        weight_sum = (
            self.evidence_alignment_weight
            + self.product_relevance_weight
            + self.campaign_fit_weight
            + self.format_fit_weight
            + self.environment_fit_weight
            + self.reference_fit_weight
        )
        if weight_sum <= 0:
            raise ValueError("at least one positive scoring weight is required")
        return self


class VisualStrategyScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_alignment: float = Field(ge=0.0, le=1.0)
    product_relevance: float = Field(ge=0.0, le=1.0)
    campaign_fit: float = Field(ge=0.0, le=1.0)
    format_fit: float = Field(ge=0.0, le=1.0)
    environment_fit: float = Field(ge=0.0, le=1.0)
    reference_fit: float = Field(ge=0.0, le=1.0)
    unsupported_inference_penalty: float = Field(ge=0.0, le=1.0)
    fallback_penalty: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)


class VisualStrategyRejectionCode(StrEnum):
    DISABLED = "disabled"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    PLACEMENT_MISMATCH = "placement_mismatch"
    CAMPAIGN_ROLE_MISMATCH = "campaign_role_mismatch"
    MISSING_PROVIDER_CAPABILITY = "missing_provider_capability"
    MISSING_REQUIRED_TAG = "missing_required_tag"
    MISSING_SOURCE_REQUIREMENT = "missing_source_requirement"
    EXCLUDED_TAG_PRESENT = "excluded_tag_present"
    PROHIBITED_VISUAL_ELEMENT = "prohibited_visual_element"
    MISSING_VISUAL_ELEMENT_EVIDENCE = "missing_visual_element_evidence"


class VisualStrategySignalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    business_signals: frozenset[str] = Field(default_factory=frozenset)
    product_signals: frozenset[str] = Field(default_factory=frozenset)
    product_visual_signals: frozenset[str] = Field(default_factory=frozenset)
    semantic_intent_signals: frozenset[str] = Field(default_factory=frozenset)
    all_signals: frozenset[str] = Field(default_factory=frozenset)
    prohibited_visual_elements: frozenset[str] = Field(default_factory=frozenset)
    campaign_roles: frozenset[str] = Field(default_factory=frozenset)
    placement: str | None = None
    available_provider_capabilities: frozenset[str] = Field(default_factory=frozenset)
    reference_style_signals: frozenset[str] = Field(default_factory=frozenset)


class VisualStrategyCandidateTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    eligible: bool
    rejection_codes: tuple[VisualStrategyRejectionCode, ...] = ()
    matched_required_tags: frozenset[str] = Field(default_factory=frozenset)
    missing_required_tags: frozenset[str] = Field(default_factory=frozenset)
    matched_preferred_tags: frozenset[str] = Field(default_factory=frozenset)
    matched_excluded_tags: frozenset[str] = Field(default_factory=frozenset)
    matched_source_requirements: tuple[str, ...] = ()
    missing_source_requirements: tuple[str, ...] = ()
    blocked_visual_elements: frozenset[str] = Field(default_factory=frozenset)
    unsupported_visual_elements: frozenset[str] = Field(default_factory=frozenset)
    score: VisualStrategyScore | None = None


class VisualStrategyResolutionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resolver_version: str
    scoring_policy_version: str
    registry_version: str
    registry_snapshot_hash: str
    candidate_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    non_fallback_eligible_count: int = Field(ge=0)
    fallback_eligible_count: int = Field(ge=0)
    selected_strategy_id: str | None
    fallback_used: bool
    candidates: tuple[VisualStrategyCandidateTrace, ...]


class VisualStrategyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    archetype: str
    composition_template_id: str
    mood_preset_id: str
    copy_tone_profile_id: str
    provider_capabilities: frozenset[str]
    score: VisualStrategyScore
    fallback_used: bool
    fallback_tier: int
    matched_rules: tuple[str, ...]
    rejected_strategy_ids: tuple[str, ...]
    registry_version: str
    registry_snapshot_hash: str
    resolver_version: str
    trace: VisualStrategyResolutionTrace
