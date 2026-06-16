"""Deterministic integrity report contracts for visual strategy registries."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from orchestrator.app.schemas.visual_strategy import normalize_required_label


class RegistryValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RegistryValidationCode(StrEnum):
    DUPLICATE_STRATEGY_ID = "duplicate_strategy_id"
    MISSING_COMPOSITION_TEMPLATE = "missing_composition_template"
    MISSING_MOOD_PRESET = "missing_mood_preset"
    MISSING_COPY_TONE_PROFILE = "missing_copy_tone_profile"
    INVALID_ARCHETYPE = "invalid_archetype"
    ARCHETYPE_CATALOG_UNAVAILABLE = "archetype_catalog_unavailable"
    REQUIRED_EXCLUDED_TAG_CONFLICT = "required_excluded_tag_conflict"
    PREFERRED_EXCLUDED_TAG_CONFLICT = "preferred_excluded_tag_conflict"
    REQUIRED_PREFERRED_TAG_CONFLICT = "required_preferred_tag_conflict"
    DUPLICATE_SOURCE_REQUIREMENT = "duplicate_source_requirement"
    DUPLICATE_VISUAL_ELEMENT_REQUIREMENT = "duplicate_visual_element_requirement"
    INTRODUCED_ELEMENT_WITHOUT_REQUIREMENT = "introduced_element_without_requirement"
    INVALID_PROVIDER_CAPABILITY = "invalid_provider_capability"
    PROVIDER_CAPABILITY_CATALOG_UNAVAILABLE = "provider_capability_catalog_unavailable"
    DISABLED_PROFILE_EXPOSED = "disabled_profile_exposed"
    MISSING_ENABLED_FALLBACK = "missing_enabled_fallback"
    FALLBACK_WITHOUT_DOMAIN_COVERAGE = "fallback_without_domain_coverage"
    EMPTY_ENABLED_REGISTRY = "empty_enabled_registry"
    REGISTRY_HASH_MISMATCH = "registry_hash_mismatch"


class RegistryValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: RegistryValidationCode
    severity: RegistryValidationSeverity
    strategy_id: str | None = None
    field_path: str | None = None
    related_id: str | None = None
    message: str

    @field_validator("strategy_id", "field_path", "related_id", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_required_label(value)

    @field_validator("message", mode="before")
    @classmethod
    def normalize_message(cls, value: Any) -> str:
        return normalize_required_label(value)


class RegistryIntegrityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "visual-strategy-registry-integrity-policy-v1"
    require_enabled_fallback: bool = True
    require_provider_capability_catalog: bool = False
    require_all_introduced_elements_grounded: bool = True
    require_fallback_domain_coverage: bool = False
    allowed_archetypes: frozenset[str] | None = None

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: Any) -> str:
        return normalize_required_label(value)

    @field_validator("allowed_archetypes", mode="before")
    @classmethod
    def normalize_allowed_archetypes(cls, value: Any) -> frozenset[str] | None:
        if value is None:
            return None
        normalized = frozenset(normalize_required_label(item) for item in value)
        return normalized


class RegistryValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validator_version: str
    registry_version: str | None
    registry_snapshot_hash: str | None
    profile_count: int
    enabled_profile_count: int
    disabled_profile_count: int
    fallback_profile_count: int
    enabled_fallback_profile_count: int
    error_count: int
    warning_count: int
    info_count: int
    valid: bool
    complete: bool
    issues: tuple[RegistryValidationIssue, ...]
    checked_composition_template_count: int
    checked_mood_preset_count: int
    checked_copy_tone_profile_count: int
    checked_provider_capability_count: int
    archetype_validation_mode: str
    provider_capability_validation_mode: str
    discriminated_union_status: str

    @field_validator(
        "validator_version",
        "archetype_validation_mode",
        "provider_capability_validation_mode",
        "discriminated_union_status",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        return normalize_required_label(value)

    @field_validator("registry_version", "registry_snapshot_hash", mode="before")
    @classmethod
    def normalize_optional_required_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_required_label(value)

    @model_validator(mode="after")
    def validate_report_counts(self) -> "RegistryValidationReport":
        error_count = sum(1 for issue in self.issues if issue.severity == RegistryValidationSeverity.ERROR)
        warning_count = sum(1 for issue in self.issues if issue.severity == RegistryValidationSeverity.WARNING)
        info_count = sum(1 for issue in self.issues if issue.severity == RegistryValidationSeverity.INFO)
        if self.error_count != error_count:
            raise ValueError("error_count must match error severity issues")
        if self.warning_count != warning_count:
            raise ValueError("warning_count must match warning severity issues")
        if self.info_count != info_count:
            raise ValueError("info_count must match info severity issues")
        if self.valid != (self.error_count == 0):
            raise ValueError("valid must equal error_count == 0")
        if self.profile_count != self.enabled_profile_count + self.disabled_profile_count:
            raise ValueError("profile counts must be internally consistent")
        if self.enabled_fallback_profile_count > self.fallback_profile_count:
            raise ValueError("enabled fallback count must not exceed fallback count")
        return self
