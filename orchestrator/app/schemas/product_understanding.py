"""Open-domain product understanding contracts."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from orchestrator.app.schemas.input_evidence import EvidenceItem


BroadCategory = Literal[
    "food_and_beverage",
    "beauty_and_personal_care",
    "fashion_and_lifestyle",
    "home_and_living",
    "technology",
    "local_service",
    "hospitality",
    "health_and_wellness",
    "education",
    "entertainment_and_media",
    "automotive",
    "other",
]


UNSUPPORTED_CLAIM_CATEGORIES = {
    "price",
    "discount",
    "promotion_period",
    "scarcity",
    "inventory",
    "social_proof",
    "review_count",
    "ranking",
    "ingredient",
    "origin",
    "manufacturing_method",
    "certification",
    "medical_effect",
    "health_effect",
    "beauty_effect",
    "performance_guarantee",
    "safety_claim",
    "environmental_claim",
    "numeric_claim",
    "comparative_superiority",
    "delivery_condition",
    "warranty",
}


_SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class ProductUnderstanding(BaseModel):
    schema_version: Literal["product_understanding_v1"] = "product_understanding_v1"
    product_name: str
    normalized_product_type: str | None = None
    broad_category: BroadCategory
    category_path: list[str]
    product_form: str | None = None
    use_contexts: list[str] = Field(default_factory=list)
    verified_facts: list[EvidenceItem] = Field(default_factory=list)
    visual_observations: list[EvidenceItem] = Field(default_factory=list)
    permissible_inferences: list[EvidenceItem] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)
    unsupported_claim_categories: list[str] = Field(default_factory=list)
    product_name_evidence_ids: list[str] = Field(default_factory=list)
    confidence_by_field: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    clarification_required: bool = False
    manual_review_required: bool = False
    provider_metadata: dict = Field(default_factory=dict)

    @field_validator("product_name")
    @classmethod
    def product_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("product_name is required")
        return value

    @field_validator("normalized_product_type")
    @classmethod
    def normalized_type_is_snake_case(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SNAKE_CASE_RE.match(normalized):
            raise ValueError("normalized_product_type must be lowercase snake_case")
        return normalized

    @field_validator("category_path")
    @classmethod
    def category_path_is_open_taxonomy(cls, value: list[str]) -> list[str]:
        if not 1 <= len(value) <= 6:
            raise ValueError("category_path length must be 1..6")
        seen: set[str] = set()
        normalized: list[str] = []
        for item in value:
            slug = item.strip().lower()
            if not _SNAKE_CASE_RE.match(slug):
                raise ValueError("category_path items must be lowercase snake_case")
            if slug in seen:
                raise ValueError("category_path cannot contain duplicates")
            seen.add(slug)
            normalized.append(slug)
        return normalized

    @field_validator("unknown_fields", "unsupported_claim_categories", "use_contexts")
    @classmethod
    def normalize_unique_slugs(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in value:
            slug = str(item).strip().lower()
            if not slug or slug in seen:
                continue
            output.append(slug)
            seen.add(slug)
        return output

    @model_validator(mode="after")
    def validate_consistency(self):
        if self.category_path[0] != self.broad_category:
            raise ValueError("category_path first item must match broad_category")
        invalid_claims = [item for item in self.unsupported_claim_categories if item not in UNSUPPORTED_CLAIM_CATEGORIES]
        if invalid_claims:
            raise ValueError(f"unsupported claim category not allowed: {invalid_claims[0]}")
        for item in self.verified_facts:
            if item.source not in {"user_text", "asset_metadata", "brand_profile", "reference_metadata"} or item.evidence_class != "verified_fact":
                raise ValueError("verified_facts must reference verified fact evidence")
        for item in self.visual_observations:
            if item.source not in {"image_vlm", "asset_metadata"} or item.evidence_class != "visual_observation":
                raise ValueError("visual_observations must reference visual observation evidence")
        for item in self.permissible_inferences:
            if item.evidence_class != "creative_inference" or item.usable_for_copy or item.confidence > 0.8:
                raise ValueError("permissible_inferences must be non-copy creative inferences with confidence <= 0.8")
        return self
