"""Creative routing boundary contracts."""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from orchestrator.app.llm.domain_routing import DomainRoutingResult
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.llm_marketing import AdFormatSpec
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("creative routing value must be a string")
    normalized = value.strip()
    return normalized or None


def normalize_string_list(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    candidates = [values] if isinstance(values, str) else values
    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("creative routing list values must be strings")
        item = value.strip()
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return normalized


def deduplicate_evidence_items(values: list[EvidenceItem]) -> list[EvidenceItem]:
    output: list[EvidenceItem] = []
    seen: dict[str, EvidenceItem] = {}
    for item in values:
        existing = seen.get(item.evidence_id)
        if existing is None:
            seen[item.evidence_id] = item
            output.append(item)
            continue
        if existing != item:
            raise ValueError(f"conflicting EvidenceItem entries share evidence_id={item.evidence_id}")
    return output


def deduplicate_input_conflicts(values: list[InputConflict]) -> list[InputConflict]:
    output: list[InputConflict] = []
    seen: dict[str, InputConflict] = {}
    for item in values:
        existing = seen.get(item.conflict_id)
        if existing is None:
            seen[item.conflict_id] = item
            output.append(item)
            continue
        if existing != item:
            raise ValueError(f"conflicting InputConflict entries share conflict_id={item.conflict_id}")
    return output


def freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): freeze_json_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json_value(item) for item in value)
    return value


def unfreeze_json_value(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: unfreeze_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [unfreeze_json_value(item) for item in value]
    return value


def copy_json_compatible_profile(value: dict[str, Any] | None) -> MappingProxyType | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("reference_style_profile must be a dict or None")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("reference_style_profile must be JSON-compatible") from exc
    return freeze_json_value(json.loads(encoded))


class CreativeRoutingContext(BaseModel):
    """Aggregator boundary for visual strategy routing inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    domain: DomainRoutingResult
    business: BusinessEnvironmentContext
    product: ProductUnderstanding
    product_visual: ProductVisualContext
    campaign: CampaignContext
    ad_format: AdFormatSpec
    visual_observations: tuple[EvidenceItem, ...] = ()
    reference_style_profile: MappingProxyType | None = None
    ambiguity_flags: tuple[str, ...] = ()
    input_conflicts: tuple[InputConflict, ...] = ()
    resolver_version: str

    @field_validator("visual_observations", mode="after")
    @classmethod
    def normalize_visual_observations(cls, value: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
        return tuple(deduplicate_evidence_items(list(value)))

    @field_validator("input_conflicts", mode="after")
    @classmethod
    def normalize_input_conflicts(cls, value: tuple[InputConflict, ...]) -> tuple[InputConflict, ...]:
        return tuple(deduplicate_input_conflicts(list(value)))

    @field_validator("reference_style_profile", mode="before")
    @classmethod
    def validate_reference_style_profile(cls, value: Any) -> MappingProxyType | None:
        return copy_json_compatible_profile(value)

    @field_validator("ambiguity_flags", mode="before")
    @classmethod
    def normalize_ambiguity_flags(cls, value: Any) -> tuple[str, ...]:
        return tuple(normalize_string_list(value))

    @field_serializer("reference_style_profile")
    def serialize_reference_style_profile(self, value: MappingProxyType | None):
        return unfreeze_json_value(value)

    @field_validator("resolver_version", mode="before")
    @classmethod
    def normalize_resolver_version(cls, value: Any) -> str:
        normalized = normalize_optional_text(value)
        if normalized is None:
            raise ValueError("resolver_version must be a non-empty string")
        return normalized

    @model_validator(mode="after")
    def validate_cross_context_invariants(self) -> "CreativeRoutingContext":
        if self.domain.canonical_domain != self.business.broad_domain:
            raise ValueError("domain canonical_domain must match business broad_domain")
        if self.product.product_name.strip() != self.product_visual.product_name.strip():
            raise ValueError("product_name must match product_visual product_name")
        if self.product.category_path or self.product_visual.category_path:
            if tuple(self.product.category_path) != tuple(self.product_visual.category_path):
                raise ValueError("product category_path must match product_visual category_path")
        return self
