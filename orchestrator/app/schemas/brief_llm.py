"""Structured brief interpretation schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


BriefBusinessType = Literal["cafe", "restaurant", "beauty", "retail", "education", "fitness", "service", "other"]
BriefPromotionGoal = Literal["new_launch", "discount_event", "brand_awareness", "reservation", "visit_increase", "seasonal_campaign", "product_detail", "other"]
BriefToneLabel = Literal["emotional", "premium", "cute", "clean", "trendy", "event", "trustworthy", "direct", "friendly", "unknown"]
BriefMissingField = Literal["business_type", "item_or_service", "promotion_goal", "target_persona", "tone", "ad_format"]


class BriefInterpreterOutput(BaseModel):
    business_type: BriefBusinessType | None = None
    item_or_service: str | None = Field(
        default=None,
        description="Keep verbatim in the user's original language; never transliterate Korean to romaji/English.",
    )
    promotion_goal: BriefPromotionGoal | None = None
    target_persona: str | None = None
    tone: BriefToneLabel | None = None
    copy_generation_mode: str | None = None
    missing_fields: list[BriefMissingField] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    unverifiable_claims: list[str] = Field(default_factory=list)
    source: str = "brief_interpreter_llm"
