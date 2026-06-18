"""Declarative visual strategy registry contracts."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain


def normalize_required_label(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("value must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


def normalize_string_set(values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        return frozenset()
    if isinstance(values, str):
        candidates: Iterable[str] = [values]
    else:
        candidates = values

    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("set values must be strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return frozenset(normalized)


def normalize_domain_set(values: Iterable[CanonicalBusinessDomain | str] | None) -> frozenset[CanonicalBusinessDomain]:
    if values is None or isinstance(values, str):
        raise ValueError("supported_domains must contain at least one canonical domain")

    normalized: list[CanonicalBusinessDomain] = []
    seen: set[CanonicalBusinessDomain] = set()
    valid_values = {domain.value: domain for domain in CanonicalBusinessDomain}
    for value in values:
        if isinstance(value, CanonicalBusinessDomain):
            domain = value
        elif isinstance(value, str) and value in valid_values:
            domain = valid_values[value]
        else:
            raise ValueError("supported_domains values must be canonical business domains")
        if domain not in seen:
            normalized.append(domain)
            seen.add(domain)

    if not normalized:
        raise ValueError("supported_domains must contain at least one canonical domain")
    return frozenset(normalized)


class VisualStrategyContextSource(StrEnum):
    """Bounded-context origin of a strategy tag requirement.

    This is distinct from RoutingEvidenceSource, which represents the original
    evidence acquisition channel such as user text or image VLM.
    """

    BUSINESS = "business"
    PRODUCT = "product"
    PRODUCT_VISUAL = "product_visual"
    PRODUCT_VISUAL_FACT = "product_visual_fact"
    PRODUCT_VISUAL_INFERENCE = "product_visual_inference"
    SEMANTIC_INTENT = "semantic_intent"
    SEMANTIC_FACT = "semantic_fact"
    SEMANTIC_STYLE = "semantic_style"


class VisualStrategyTagRequirement(BaseModel):
    """Tags required from a specific upstream bounded context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: VisualStrategyContextSource
    all_of: frozenset[str] = Field(default_factory=frozenset)
    any_of: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("all_of", "any_of", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> frozenset[str]:
        return normalize_string_set(value)

    @model_validator(mode="after")
    def validate_requirement(self) -> "VisualStrategyTagRequirement":
        if not self.all_of and not self.any_of:
            raise ValueError("tag requirement must include all_of or any_of")
        overlap = self.all_of & self.any_of
        if overlap:
            raise ValueError(f"tag requirement cannot require the same tag twice: {sorted(overlap)[0]}")
        return self


class VisualElementEvidenceRequirement(BaseModel):
    """Evidence required before a strategy may introduce a visual element."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    element: str
    requirements: tuple[VisualStrategyTagRequirement, ...]

    @field_validator("element", mode="before")
    @classmethod
    def normalize_element(cls, value: Any) -> str:
        return normalize_required_label(value)

    @field_validator("requirements", mode="before")
    @classmethod
    def validate_requirements(cls, value: Any) -> tuple[VisualStrategyTagRequirement, ...]:
        if value is None:
            raise ValueError("visual element evidence requirements must not be empty")
        requirements = tuple(value)
        if not requirements:
            raise ValueError("visual element evidence requirements must not be empty")
        return requirements


class VisualStrategyResourceCatalog(BaseModel):
    """Available resource IDs used to validate visual strategy profiles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    composition_template_ids: frozenset[str]
    mood_preset_ids: frozenset[str]
    copy_tone_profile_ids: frozenset[str]
    provider_capability_ids: frozenset[str] | None = None

    @field_validator(
        "composition_template_ids",
        "mood_preset_ids",
        "copy_tone_profile_ids",
        "provider_capability_ids",
        mode="before",
    )
    @classmethod
    def normalize_ids(cls, value: Any, info: ValidationInfo) -> frozenset[str] | None:
        if value is None:
            return None
        normalized = normalize_string_set(value)
        if info.field_name == "provider_capability_ids":
            return normalized
        if not normalized:
            raise ValueError("resource catalog ID sets must not be empty")
        return normalized


class VisualStrategyProfile(BaseModel):
    """Declarative visual strategy capability profile.

    This model describes strategy applicability and resource references only.
    It must not perform product-specific selection, scoring, fallback, provider
    routing, prompt generation, or scene planning.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    archetype: str

    supported_domains: frozenset[CanonicalBusinessDomain]
    supported_campaign_roles: frozenset[str] = Field(default_factory=frozenset)
    supported_placements: frozenset[str] = Field(default_factory=frozenset)

    required_tags: frozenset[str] = Field(default_factory=frozenset)
    preferred_tags: frozenset[str] = Field(default_factory=frozenset)
    excluded_tags: frozenset[str] = Field(default_factory=frozenset)
    required_tag_requirements: tuple[VisualStrategyTagRequirement, ...] = ()
    introduced_visual_elements: frozenset[str] = Field(default_factory=frozenset)
    visual_element_evidence_requirements: tuple[VisualElementEvidenceRequirement, ...] = ()

    composition_template_id: str
    mood_preset_id: str
    copy_tone_profile_id: str

    provider_capabilities: frozenset[str] = Field(default_factory=frozenset)

    priority: int = Field(ge=0)
    fallback_tier: int = Field(default=0, ge=0)
    fallback_role: str | None = None
    enabled: bool

    @field_validator(
        "strategy_id",
        "archetype",
        "composition_template_id",
        "mood_preset_id",
        "copy_tone_profile_id",
        "fallback_role",
        mode="before",
    )
    @classmethod
    def normalize_label(cls, value: Any, info: ValidationInfo) -> str | None:
        if info.field_name == "fallback_role" and value is None:
            return None
        return normalize_required_label(value)

    @field_validator("supported_domains", mode="before")
    @classmethod
    def normalize_domains(cls, value: Any) -> frozenset[CanonicalBusinessDomain]:
        return normalize_domain_set(value)

    @field_validator(
        "supported_campaign_roles",
        "supported_placements",
        "required_tags",
        "preferred_tags",
        "excluded_tags",
        "provider_capabilities",
        "introduced_visual_elements",
        mode="before",
    )
    @classmethod
    def normalize_sets(cls, value: Any) -> frozenset[str]:
        return normalize_string_set(value)

    @field_validator("enabled", mode="before")
    @classmethod
    def validate_strict_bool(cls, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValueError("enabled must be a boolean")
        return value

    @field_validator("priority", mode="before")
    @classmethod
    def validate_strict_priority(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("priority must be an integer")
        if value < 0:
            raise ValueError("priority must be non-negative")
        return value

    @field_validator("fallback_tier", mode="before")
    @classmethod
    def validate_strict_fallback_tier(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("fallback_tier must be an integer")
        if value < 0:
            raise ValueError("fallback_tier must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_tag_conflicts(self) -> "VisualStrategyProfile":
        required_excluded = self.required_tags & self.excluded_tags
        if required_excluded:
            raise ValueError(f"required tag cannot also be excluded: {sorted(required_excluded)[0]}")

        preferred_excluded = self.preferred_tags & self.excluded_tags
        if preferred_excluded:
            raise ValueError(f"preferred tag cannot also be excluded: {sorted(preferred_excluded)[0]}")

        required_preferred = self.required_tags & self.preferred_tags
        if required_preferred:
            raise ValueError(f"required tag cannot also be preferred: {sorted(required_preferred)[0]}")

        requirement_elements = [requirement.element for requirement in self.visual_element_evidence_requirements]
        duplicate_elements = {element for element in requirement_elements if requirement_elements.count(element) > 1}
        if duplicate_elements:
            raise ValueError(f"duplicate visual element evidence requirement: {sorted(duplicate_elements)[0]}")

        missing_elements = set(requirement_elements) - set(self.introduced_visual_elements)
        if missing_elements:
            raise ValueError(f"visual element evidence requirement references unknown element: {sorted(missing_elements)[0]}")

        if self.enabled and self.fallback_tier == 0:
            required_elements = {requirement.element for requirement in self.visual_element_evidence_requirements}
            unbacked_elements = set(self.introduced_visual_elements) - required_elements
            if unbacked_elements:
                raise ValueError(f"enabled non-fallback introduced visual element requires evidence: {sorted(unbacked_elements)[0]}")

        if self.fallback_tier == 0 and self.fallback_role is not None:
            raise ValueError("primary profile must not include fallback_role")
        if self.fallback_tier > 0 and self.fallback_role is None:
            raise ValueError("fallback profile requires fallback_role")

        return self
