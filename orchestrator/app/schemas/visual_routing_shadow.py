"""Contracts for visual route shadow execution and comparison."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from orchestrator.app.llm.domain_routing import LegacyVisualRouteKey
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyFallbackReason


def _normalize_required_string(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must be a non-empty string")
    return normalized


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(value)


class RoutingMode(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"


class RoutingSource(StrEnum):
    LEGACY = "legacy"
    CANONICAL = "canonical"


class RoutingFailurePolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"


class RoutingExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: RoutingMode
    run_legacy: StrictBool
    run_canonical: StrictBool
    active_source: RoutingSource
    canonical_failure_policy: RoutingFailurePolicy

    @model_validator(mode="after")
    def validate_plan_matrix(self) -> "RoutingExecutionPlan":
        expected = {
            RoutingMode.LEGACY: (True, False, RoutingSource.LEGACY, RoutingFailurePolicy.NOT_APPLICABLE),
            RoutingMode.SHADOW: (True, True, RoutingSource.LEGACY, RoutingFailurePolicy.FAIL_OPEN),
            RoutingMode.CANONICAL: (False, True, RoutingSource.CANONICAL, RoutingFailurePolicy.FAIL_CLOSED),
        }[self.mode]
        actual = (
            self.run_legacy,
            self.run_canonical,
            self.active_source,
            self.canonical_failure_policy,
        )
        if actual != expected:
            raise ValueError("routing execution plan must match mode matrix")
        return self


class LegacyVisualRouteObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    legacy_route_key: LegacyVisualRouteKey | None = None
    preset_id: str
    template_id: str
    copy_tone_profile_id: str | None = None
    route_family_id: str | None = None
    route_version: str | None = None

    @field_validator("preset_id", "template_id", mode="before")
    @classmethod
    def normalize_required_label(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @field_validator("copy_tone_profile_id", "route_family_id", "route_version", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return _normalize_optional_string(value)


class RouteDisagreementCode(StrEnum):
    PRESET_MISMATCH = "preset_mismatch"
    TEMPLATE_MISMATCH = "template_mismatch"
    COPY_TONE_MISMATCH = "copy_tone_mismatch"
    FAMILY_MISMATCH = "family_mismatch"


class RouteComparisonLimitation(StrEnum):
    FAMILY_METADATA_UNAVAILABLE = "family_metadata_unavailable"


class RouteComparisonSeverity(StrEnum):
    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class RouteComparisonPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    limitation_severity: RouteComparisonSeverity = RouteComparisonSeverity.INFO
    single_resource_mismatch_severity: RouteComparisonSeverity = RouteComparisonSeverity.WARNING
    multiple_resource_mismatch_severity: RouteComparisonSeverity = RouteComparisonSeverity.HIGH
    family_mismatch_severity: RouteComparisonSeverity = RouteComparisonSeverity.HIGH

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: Any) -> str:
        return _normalize_required_string(value)


class RouteComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_version: str
    comparison_policy_version: str
    legacy_route_key: LegacyVisualRouteKey | None = None
    legacy_route_version: str | None = None
    legacy_preset_id: str
    legacy_template_id: str
    legacy_copy_tone_profile_id: str | None = None
    new_strategy_id: str
    new_preset_id: str
    new_template_id: str
    new_copy_tone_profile_id: str
    legacy_family_id: str | None = None
    new_family_id: str | None = None
    preset_match: StrictBool
    template_match: StrictBool
    copy_tone_match: StrictBool | None
    family_match: StrictBool | None
    disagreement_codes: tuple[RouteDisagreementCode, ...]
    comparison_limitations: tuple[RouteComparisonLimitation, ...] = ()
    severity: RouteComparisonSeverity
    limitation_severity: RouteComparisonSeverity = RouteComparisonSeverity.NONE
    new_route_version: str
    new_resolver_version: str
    new_registry_version: str
    new_registry_snapshot_hash: str
    canonical_fallback_used: StrictBool
    canonical_fallback_role: str | None = None
    canonical_fallback_reason: VisualStrategyFallbackReason | None = None
    canonical_unsupported_domain: StrictBool = False
    canonical_missing_specialized_profile: StrictBool = False

    @field_validator(
        "comparison_version",
        "comparison_policy_version",
        "legacy_preset_id",
        "legacy_template_id",
        "new_strategy_id",
        "new_preset_id",
        "new_template_id",
        "new_copy_tone_profile_id",
        "new_route_version",
        "new_resolver_version",
        "new_registry_version",
        "new_registry_snapshot_hash",
        mode="before",
    )
    @classmethod
    def normalize_required_label(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @field_validator(
        "legacy_copy_tone_profile_id",
        "legacy_route_version",
        "legacy_family_id",
        "new_family_id",
        "canonical_fallback_role",
        mode="before",
    )
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return _normalize_optional_string(value)

    @model_validator(mode="after")
    def validate_comparison_integrity(self) -> "RouteComparison":
        codes = set(self.disagreement_codes)
        limitations = set(self.comparison_limitations)

        if len(codes) != len(self.disagreement_codes):
            raise ValueError("disagreement codes must be unique")
        if len(limitations) != len(self.comparison_limitations):
            raise ValueError("comparison limitations must be unique")
        if not limitations and self.limitation_severity != RouteComparisonSeverity.NONE:
            raise ValueError("missing comparison limitations require none limitation severity")
        if limitations and self.limitation_severity == RouteComparisonSeverity.NONE:
            raise ValueError("comparison limitations require limitation severity")
        if self.preset_match == (RouteDisagreementCode.PRESET_MISMATCH in codes):
            raise ValueError("preset match and disagreement code conflict")
        if self.template_match == (RouteDisagreementCode.TEMPLATE_MISMATCH in codes):
            raise ValueError("template match and disagreement code conflict")
        if self.copy_tone_match is None:
            if self.legacy_copy_tone_profile_id is not None:
                raise ValueError("copy tone match must be known when legacy copy tone exists")
            if RouteDisagreementCode.COPY_TONE_MISMATCH in codes:
                raise ValueError("unknown copy tone comparison cannot include mismatch")
        elif self.copy_tone_match == (RouteDisagreementCode.COPY_TONE_MISMATCH in codes):
            raise ValueError("copy tone match and disagreement code conflict")
        if self.family_match is None:
            if RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE not in limitations:
                raise ValueError("unknown family comparison must be recorded as a limitation")
            if RouteDisagreementCode.FAMILY_MISMATCH in codes:
                raise ValueError("unknown family comparison cannot include mismatch")
        else:
            if RouteComparisonLimitation.FAMILY_METADATA_UNAVAILABLE in limitations:
                raise ValueError("known family comparison cannot be unavailable")
            if self.family_match == (RouteDisagreementCode.FAMILY_MISMATCH in codes):
                raise ValueError("family match and disagreement code conflict")
        if codes and self.severity == RouteComparisonSeverity.NONE:
            raise ValueError("mismatch disagreement cannot have none severity")
        if not self.canonical_fallback_used:
            if self.canonical_fallback_role is not None or self.canonical_fallback_reason is not None:
                raise ValueError("non-fallback comparison must not include fallback metadata")
            if self.canonical_unsupported_domain or self.canonical_missing_specialized_profile:
                raise ValueError("non-fallback comparison must not include fallback diagnostics")
        else:
            if self.canonical_fallback_role is None or self.canonical_fallback_reason is None:
                raise ValueError("fallback comparison requires fallback metadata")
        if self.canonical_unsupported_domain and self.canonical_missing_specialized_profile:
            raise ValueError("fallback diagnostics are mutually exclusive")
        if self.canonical_fallback_reason == VisualStrategyFallbackReason.UNSUPPORTED_DOMAIN:
            if not self.canonical_unsupported_domain or self.canonical_missing_specialized_profile:
                raise ValueError("unsupported-domain fallback diagnosis mismatch")
        if self.canonical_fallback_reason == VisualStrategyFallbackReason.MISSING_SPECIALIZED_PROFILE:
            if not self.canonical_missing_specialized_profile or self.canonical_unsupported_domain:
                raise ValueError("missing-specialized fallback diagnosis mismatch")
        return self


class ShadowRoutingErrorStage(StrEnum):
    CANONICAL_RESOLUTION = "canonical_resolution"
    LEGACY_OBSERVATION = "legacy_observation"
    ROUTE_COMPARISON = "route_comparison"


class ShadowRoutingErrorCode(StrEnum):
    NO_ELIGIBLE_CANONICAL_STRATEGY = "no_eligible_canonical_strategy"
    CANONICAL_RESOLUTION_FAILED = "canonical_resolution_failed"
    LEGACY_OBSERVATION_FAILED = "legacy_observation_failed"
    ROUTE_COMPARISON_FAILED = "route_comparison_failed"


class ShadowRoutingError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: ShadowRoutingErrorStage
    code: ShadowRoutingErrorCode
    exception_type: str

    @field_validator("exception_type", mode="before")
    @classmethod
    def normalize_exception_type(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @model_validator(mode="after")
    def validate_stage_code_matrix(self) -> "ShadowRoutingError":
        expected = {
            ShadowRoutingErrorStage.CANONICAL_RESOLUTION: {
                ShadowRoutingErrorCode.NO_ELIGIBLE_CANONICAL_STRATEGY,
                ShadowRoutingErrorCode.CANONICAL_RESOLUTION_FAILED,
            },
            ShadowRoutingErrorStage.LEGACY_OBSERVATION: {ShadowRoutingErrorCode.LEGACY_OBSERVATION_FAILED},
            ShadowRoutingErrorStage.ROUTE_COMPARISON: {ShadowRoutingErrorCode.ROUTE_COMPARISON_FAILED},
        }[self.stage]
        if self.code not in expected:
            raise ValueError("shadow routing error stage and code conflict")
        return self


def build_default_route_comparison_policy() -> RouteComparisonPolicy:
    return RouteComparisonPolicy(version="visual-route-comparison-policy-v2")
