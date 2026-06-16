"""Creative routing boundary contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orchestrator.app.llm.domain_routing import DomainRoutingResult
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import normalize_string_list, normalize_optional_text
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.llm_marketing import AdFormatSpec
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext


def deduplicate_evidence_items(values: list[EvidenceItem]) -> list[EvidenceItem]:
    output: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in values:
        if item.evidence_id in seen:
            continue
        output.append(item)
        seen.add(item.evidence_id)
    return output


def deduplicate_input_conflicts(values: list[InputConflict]) -> list[InputConflict]:
    output: list[InputConflict] = []
    seen: set[str] = set()
    for item in values:
        if item.conflict_id in seen:
            continue
        output.append(item)
        seen.add(item.conflict_id)
    return output


def copy_json_compatible_profile(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("reference_style_profile must be a dict or None")
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("reference_style_profile must be JSON-compatible") from exc
    return deepcopy(value)


class CreativeRoutingContext(BaseModel):
    """Aggregator boundary for visual strategy routing inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: DomainRoutingResult
    business: BusinessEnvironmentContext
    product: ProductUnderstanding
    product_visual: ProductVisualContext
    campaign: CampaignContext
    ad_format: AdFormatSpec
    visual_observations: list[EvidenceItem] = Field(default_factory=list)
    reference_style_profile: dict[str, Any] | None = None
    ambiguity_flags: list[str] = Field(default_factory=list)
    input_conflicts: list[InputConflict] = Field(default_factory=list)
    resolver_version: str

    @field_validator("visual_observations", mode="after")
    @classmethod
    def normalize_visual_observations(cls, value: list[EvidenceItem]) -> list[EvidenceItem]:
        return deduplicate_evidence_items(value)

    @field_validator("input_conflicts", mode="after")
    @classmethod
    def normalize_input_conflicts(cls, value: list[InputConflict]) -> list[InputConflict]:
        return deduplicate_input_conflicts(value)

    @field_validator("reference_style_profile", mode="before")
    @classmethod
    def validate_reference_style_profile(cls, value: Any) -> dict[str, Any] | None:
        return copy_json_compatible_profile(value)

    @field_validator("ambiguity_flags", mode="before")
    @classmethod
    def normalize_ambiguity_flags(cls, value: Any) -> list[str]:
        return normalize_string_list(value)

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
            if self.product.category_path != self.product_visual.category_path:
                raise ValueError("product category_path must match product_visual category_path")
        return self
