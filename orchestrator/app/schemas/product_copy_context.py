"""Schemas for product-aware minimal copy planning."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MessageTerritory(BaseModel):
    territory_id: str
    label: str
    rationale: str
    supporting_evidence_keys: list[str] = Field(default_factory=list)
    suitability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    visual_fit_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"] = "low"


class DynamicLanguagePolicy(BaseModel):
    primary_language: Literal["korean", "english", "mixed"] = "korean"
    headline_language: Literal["korean", "english", "mixed"] = "korean"
    supporting_copy_language: Literal["korean", "english", "mixed"] = "korean"
    english_headline_allowed: bool = False
    bilingual_allowed: bool = False
    romanization_allowed: bool = False
    rationale: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class MinimalCopyPresencePlan(BaseModel):
    mode: Literal["image_only", "brand_only", "headline_only", "headline_plus_support", "headline_plus_closing"]
    allowed_roles: list[Literal["brand_label", "headline", "supporting_copy", "closing_copy", "embedded_action_cta"]]
    max_text_blocks: int = Field(ge=0, le=2)
    max_total_characters: int = Field(ge=0, le=80)
    max_text_area_ratio: float = Field(ge=0.0, le=0.12)
    no_text_allowed: bool
    rationale: list[str] = Field(default_factory=list)


class InteractionCopyPlan(BaseModel):
    interaction_mode: Literal["non_interactive_image", "platform_interactive", "landing_page", "offline_with_action"] = "non_interactive_image"
    action_cta_allowed: bool = False
    selected_role: Literal["none", "platform_only", "embedded_action_cta", "closing_copy", "tagline", "proof_line", "offer_line"] = "none"
    action_destination_verified: bool = False
    rationale: list[str] = Field(default_factory=list)


class ProductCopyContext(BaseModel):
    product_name: str
    normalized_product_type: str | None = None
    broad_category: str = "other"
    category_path: list[str] = Field(default_factory=list)
    message_territories: list[MessageTerritory] = Field(default_factory=list)
    sensory_vocabulary: list[str] = Field(default_factory=list)
    emotional_vocabulary: list[str] = Field(default_factory=list)
    functional_vocabulary: list[str] = Field(default_factory=list)
    contextual_vocabulary: list[str] = Field(default_factory=list)
    product_entities: list[str] = Field(default_factory=list)
    adjacent_entities: list[str] = Field(default_factory=list)
    excluded_territories: list[str] = Field(default_factory=list)
    customer_moments: list[str] = Field(default_factory=list)
    language_policy: DynamicLanguagePolicy
    copy_presence_plan: MinimalCopyPresencePlan
    interaction_plan: InteractionCopyPlan
    supported_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class MinimalCopyCandidate(BaseModel):
    candidate_id: str
    variant_type: Literal["image_only", "headline_only", "headline_plus_support", "headline_plus_closing"]
    territory_id: str | None = None
    headline: str | None = None
    supporting_copy: str | None = None
    closing_copy: str | None = None
    action_cta: str | None = None
    language_mode: Literal["korean", "english", "mixed"] = "korean"
    supporting_evidence_keys: list[str] = Field(default_factory=list)
    text_block_count: int = Field(ge=0, le=2)
    estimated_text_area_ratio: float = Field(ge=0.0, le=0.12)
