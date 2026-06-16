"""Visual routing diagnostic trace contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain, LegacyVisualRouteKey
from orchestrator.app.schemas.visual_routing_shadow import (
    LegacyVisualRouteObservation,
    RouteComparison,
    RoutingMode,
    RoutingSource,
    ShadowRoutingError,
)
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyFallbackReason


VISUAL_ROUTING_TRACE_VERSION = "visual-routing-trace-v1"
_ERROR_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_ARTIFACT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


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


def _normalize_raw_business_type(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    if len(normalized) > 80 or "\n" in normalized or "\r" in normalized:
        raise ValueError("raw_business_type must be a short scalar")
    return normalized


def _normalize_error_type(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    if len(normalized) > 120 or not _ERROR_TYPE_RE.match(normalized):
        raise ValueError("error_type must be an exception class identifier")
    return normalized


def normalize_trace_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        candidates = [values]
    else:
        candidates = values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        item = value.strip()
        if not item:
            continue
        if item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


def normalize_artifact_refs(values: Any) -> tuple[str, ...]:
    refs = normalize_trace_strings(values)
    for ref in refs:
        if (
            not _ARTIFACT_REF_RE.match(ref)
            or "/" in ref
            or "\\" in ref
            or "://" in ref
            or "bucket" in ref.lower()
            or "object_key" in ref.lower()
            or "base64" in ref.lower()
        ):
            raise ValueError("artifact_refs must contain opaque artifact IDs only")
    return refs


class VisualRoutingTraceCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class VisualRoutingDiagnosticStage(StrEnum):
    PRODUCT_UNDERSTANDING = "product_understanding"
    BUSINESS_NORMALIZATION = "business_normalization"
    STRATEGY_RESOLUTION = "strategy_resolution"
    RESOURCE_REGISTRY = "resource_registry"
    PROVIDER_PROMPT_ADAPTER = "provider_prompt_adapter"
    IMAGE_GENERATION = "image_generation"


class VisualRoutingStageStatus(StrEnum):
    NOT_RUN = "not_run"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class VisualRoutingInputSnapshot(BaseModel):
    """Sanitized routing input projection.

    raw_business_type is limited to the scalar business_type supplied by the
    brief or marketing context. It must not contain the full prompt, full brief,
    OCR text, user message, or product description prose.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_business_type: str | None = None
    canonical_domain: CanonicalBusinessDomain
    legacy_visual_key: LegacyVisualRouteKey | None = None
    product_name: str
    product_category_path: tuple[str, ...] = ()
    product_visual_category_path: tuple[str, ...] = ()
    category_path_match: bool
    business_tags: tuple[str, ...] = ()
    product_tags: tuple[str, ...] = ()
    campaign_roles: tuple[str, ...] = ()
    placement: str | None = None
    ambiguity_flags: tuple[str, ...] = ()
    input_conflict_ids: tuple[str, ...] = ()
    input_conflict_types: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @field_validator("raw_business_type", mode="before")
    @classmethod
    def normalize_raw_business_type(cls, value: Any) -> str | None:
        return _normalize_raw_business_type(value)

    @field_validator("placement", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return _normalize_optional_string(value)

    @field_validator("product_name", mode="before")
    @classmethod
    def normalize_product_name(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @field_validator(
        "product_category_path",
        "product_visual_category_path",
        "business_tags",
        "product_tags",
        "campaign_roles",
        "ambiguity_flags",
        "input_conflict_ids",
        "input_conflict_types",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def normalize_string_tuple(cls, value: Any) -> tuple[str, ...]:
        return normalize_trace_strings(value)


class ActiveVisualRouteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: RoutingSource
    strategy_id: str | None = None
    template_id: str
    preset_id: str
    copy_tone_profile_id: str | None = None
    route_version: str | None = None

    @field_validator("strategy_id", "copy_tone_profile_id", "route_version", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return _normalize_optional_string(value)

    @field_validator("template_id", "preset_id", mode="before")
    @classmethod
    def normalize_required_label(cls, value: Any) -> str:
        return _normalize_required_string(value)


class CanonicalVisualStrategySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    archetype: str
    template_id: str
    preset_id: str
    copy_tone_profile_id: str
    route_version: str
    resolver_version: str
    registry_version: str
    registry_snapshot_hash: str
    matched_rules: tuple[str, ...] = ()
    rejected_strategy_ids: tuple[str, ...] = ()
    eligible_not_selected_strategy_ids: tuple[str, ...] = ()
    fallback_used: StrictBool
    fallback_role: str | None = None
    fallback_reason: VisualStrategyFallbackReason | None = None
    unsupported_domain: StrictBool
    missing_specialized_profile: StrictBool
    confidence: float = Field(ge=0.0, le=1.0)
    total_score: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = ()

    @field_validator(
        "strategy_id",
        "archetype",
        "template_id",
        "preset_id",
        "copy_tone_profile_id",
        "route_version",
        "resolver_version",
        "registry_version",
        "registry_snapshot_hash",
        mode="before",
    )
    @classmethod
    def normalize_required_label(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @field_validator("fallback_role", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: Any) -> str | None:
        return _normalize_optional_string(value)

    @field_validator("matched_rules", "rejected_strategy_ids", "eligible_not_selected_strategy_ids", "evidence_refs", mode="before")
    @classmethod
    def normalize_string_tuple(cls, value: Any) -> tuple[str, ...]:
        return normalize_trace_strings(value)

    @model_validator(mode="after")
    def validate_fallback_state(self) -> "CanonicalVisualStrategySummary":
        if not self.fallback_used:
            if self.fallback_role is not None or self.fallback_reason is not None:
                raise ValueError("non-fallback summary must not include fallback metadata")
            if self.unsupported_domain or self.missing_specialized_profile:
                raise ValueError("non-fallback summary must not include fallback diagnostics")
        else:
            if self.fallback_role is None or self.fallback_reason is None:
                raise ValueError("fallback summary requires fallback metadata")
        if self.unsupported_domain and self.missing_specialized_profile:
            raise ValueError("fallback diagnostics are mutually exclusive")
        return self


class VisualRoutingStageObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: VisualRoutingDiagnosticStage
    status: VisualRoutingStageStatus
    diagnostic_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    error_type: str | None = None

    @field_validator("diagnostic_codes", "evidence_refs", mode="before")
    @classmethod
    def normalize_string_tuple(cls, value: Any) -> tuple[str, ...]:
        return normalize_trace_strings(value)

    @field_validator("artifact_refs", mode="before")
    @classmethod
    def normalize_artifact_refs(cls, value: Any) -> tuple[str, ...]:
        return normalize_artifact_refs(value)

    @field_validator("error_type", mode="before")
    @classmethod
    def normalize_error_type(cls, value: Any) -> str | None:
        return _normalize_error_type(value)

    @model_validator(mode="after")
    def validate_status_payload(self) -> "VisualRoutingStageObservation":
        if self.status == VisualRoutingStageStatus.FAILED and self.error_type is None:
            raise ValueError("failed stage requires error_type")
        if self.status == VisualRoutingStageStatus.SUCCEEDED and self.error_type is not None:
            raise ValueError("succeeded stage must not include error_type")
        if self.status == VisualRoutingStageStatus.DEGRADED and not self.diagnostic_codes:
            raise ValueError("degraded stage requires diagnostic_codes")
        if self.status in {VisualRoutingStageStatus.NOT_RUN, VisualRoutingStageStatus.UNAVAILABLE} and self.error_type is not None:
            raise ValueError("not-run or unavailable stage must not include error_type")
        return self


_STAGE_ORDER = {
    stage: index
    for index, stage in enumerate(
        (
            VisualRoutingDiagnosticStage.PRODUCT_UNDERSTANDING,
            VisualRoutingDiagnosticStage.BUSINESS_NORMALIZATION,
            VisualRoutingDiagnosticStage.STRATEGY_RESOLUTION,
            VisualRoutingDiagnosticStage.RESOURCE_REGISTRY,
            VisualRoutingDiagnosticStage.PROVIDER_PROMPT_ADAPTER,
            VisualRoutingDiagnosticStage.IMAGE_GENERATION,
        )
    )
}


class BaseVisualRoutingTrace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_version: str
    routing_mode: RoutingMode
    completeness: VisualRoutingTraceCompleteness
    input_snapshot: VisualRoutingInputSnapshot
    active_route: ActiveVisualRouteSummary | None
    stage_observations: tuple[VisualRoutingStageObservation, ...] = ()
    route_disagreement: RouteComparison | None = None

    @field_validator("trace_version", mode="before")
    @classmethod
    def normalize_trace_version(cls, value: Any) -> str:
        return _normalize_required_string(value)

    @field_validator("stage_observations", mode="after")
    @classmethod
    def sort_stage_observations(
        cls,
        value: tuple[VisualRoutingStageObservation, ...],
    ) -> tuple[VisualRoutingStageObservation, ...]:
        return tuple(sorted(value, key=lambda item: _STAGE_ORDER[item.stage]))

    @model_validator(mode="after")
    def validate_base_trace(self) -> "BaseVisualRoutingTrace":
        if self.trace_version != VISUAL_ROUTING_TRACE_VERSION:
            raise ValueError("trace_version must match visual routing trace contract")
        stages = [item.stage for item in self.stage_observations]
        if len(stages) != len(set(stages)):
            raise ValueError("stage_observations must contain each stage at most once")
        return self


class LegacyVisualRoutingTrace(BaseVisualRoutingTrace):
    routing_mode: Literal[RoutingMode.LEGACY]
    legacy_observation: LegacyVisualRouteObservation
    canonical_decision: None = None
    route_disagreement: None = None
    shadow_error: None = None

    @model_validator(mode="after")
    def validate_legacy_trace(self) -> "LegacyVisualRoutingTrace":
        if self.completeness != VisualRoutingTraceCompleteness.COMPLETE:
            raise ValueError("legacy trace requires complete routing data")
        if self.active_route is None:
            raise ValueError("legacy trace requires active route")
        if self.active_route.source != RoutingSource.LEGACY:
            raise ValueError("legacy trace active route must be legacy")
        if self.active_route.strategy_id is not None:
            raise ValueError("legacy active route must not include strategy_id")
        _assert_active_matches_legacy(self.active_route, self.legacy_observation)
        return self


class ShadowVisualRoutingTrace(BaseVisualRoutingTrace):
    routing_mode: Literal[RoutingMode.SHADOW]
    legacy_observation: LegacyVisualRouteObservation | None = None
    canonical_decision: CanonicalVisualStrategySummary | None = None
    shadow_error: ShadowRoutingError | None = None

    @model_validator(mode="after")
    def validate_shadow_trace(self) -> "ShadowVisualRoutingTrace":
        if self.shadow_error is None:
            if self.completeness != VisualRoutingTraceCompleteness.COMPLETE:
                raise ValueError("successful shadow trace must be complete")
            if self.active_route is None:
                raise ValueError("successful shadow trace requires active route")
            if self.active_route.source != RoutingSource.LEGACY:
                raise ValueError("shadow trace active route must be legacy")
            if self.active_route.strategy_id is not None:
                raise ValueError("shadow legacy active route must not include strategy_id")
            if self.legacy_observation is None or self.canonical_decision is None or self.route_disagreement is None:
                raise ValueError("successful shadow trace requires legacy, canonical, and comparison data")
            _assert_active_matches_legacy(self.active_route, self.legacy_observation)
            _assert_comparison_matches(self.route_disagreement, self.legacy_observation, self.canonical_decision)
        else:
            if self.completeness != VisualRoutingTraceCompleteness.PARTIAL:
                raise ValueError("failed shadow trace must be partial")
            if self.route_disagreement is not None:
                raise ValueError("failed shadow trace must not include route comparison")
            if self.active_route is not None:
                if self.active_route.source != RoutingSource.LEGACY:
                    raise ValueError("shadow trace active route must be legacy")
                if self.active_route.strategy_id is not None:
                    raise ValueError("shadow legacy active route must not include strategy_id")
            if self.legacy_observation is not None:
                if self.active_route is None:
                    raise ValueError("shadow trace with legacy observation requires active route")
                _assert_active_matches_legacy(self.active_route, self.legacy_observation)
        return self


class CanonicalVisualRoutingTrace(BaseVisualRoutingTrace):
    routing_mode: Literal[RoutingMode.CANONICAL]
    legacy_observation: None = None
    canonical_decision: CanonicalVisualStrategySummary
    route_disagreement: None = None
    shadow_error: None = None

    @model_validator(mode="after")
    def validate_canonical_trace(self) -> "CanonicalVisualRoutingTrace":
        if self.completeness != VisualRoutingTraceCompleteness.COMPLETE:
            raise ValueError("canonical trace requires complete routing data")
        if self.active_route is None:
            raise ValueError("canonical trace requires active route")
        if self.active_route.source != RoutingSource.CANONICAL:
            raise ValueError("canonical trace active route must be canonical")
        if self.active_route.strategy_id != self.canonical_decision.strategy_id:
            raise ValueError("canonical active route strategy must match decision")
        if self.active_route.template_id != self.canonical_decision.template_id:
            raise ValueError("canonical active route template must match decision")
        if self.active_route.preset_id != self.canonical_decision.preset_id:
            raise ValueError("canonical active route preset must match decision")
        if self.active_route.copy_tone_profile_id != self.canonical_decision.copy_tone_profile_id:
            raise ValueError("canonical active route copy tone must match decision")
        if self.active_route.route_version != self.canonical_decision.route_version:
            raise ValueError("canonical active route version must match decision")
        return self


VisualRoutingTrace = Annotated[
    LegacyVisualRoutingTrace | ShadowVisualRoutingTrace | CanonicalVisualRoutingTrace,
    Field(discriminator="routing_mode"),
]


def _assert_active_matches_legacy(active: ActiveVisualRouteSummary, legacy: LegacyVisualRouteObservation) -> None:
    if active.template_id != legacy.template_id:
        raise ValueError("active route template must match legacy observation")
    if active.preset_id != legacy.preset_id:
        raise ValueError("active route preset must match legacy observation")
    if active.copy_tone_profile_id != legacy.copy_tone_profile_id:
        raise ValueError("active route copy tone must match legacy observation")
    if active.route_version != legacy.route_version:
        raise ValueError("active route version must match legacy observation")


def _assert_comparison_matches(
    comparison: RouteComparison,
    legacy: LegacyVisualRouteObservation,
    canonical: CanonicalVisualStrategySummary,
) -> None:
    if comparison.legacy_preset_id != legacy.preset_id:
        raise ValueError("comparison legacy preset must match legacy observation")
    if comparison.legacy_template_id != legacy.template_id:
        raise ValueError("comparison legacy template must match legacy observation")
    if comparison.legacy_copy_tone_profile_id != legacy.copy_tone_profile_id:
        raise ValueError("comparison legacy copy tone must match legacy observation")
    if comparison.new_strategy_id != canonical.strategy_id:
        raise ValueError("comparison strategy must match canonical decision")
    if comparison.new_template_id != canonical.template_id:
        raise ValueError("comparison template must match canonical decision")
    if comparison.new_preset_id != canonical.preset_id:
        raise ValueError("comparison preset must match canonical decision")
