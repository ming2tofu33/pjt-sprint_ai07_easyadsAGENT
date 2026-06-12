"""Build product copy context from ProductUnderstanding and evidence."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.product_understanding_policy import normalize_slug
from orchestrator.app.schemas.product_copy_context import (
    DynamicLanguagePolicy,
    InteractionCopyPlan,
    MessageTerritory,
    MinimalCopyPresencePlan,
    ProductCopyContext,
)
from orchestrator.app.schemas.product_understanding import UNSUPPORTED_CLAIM_CATEGORIES


def build_dynamic_product_copy_context(context: dict[str, Any], understanding: dict[str, Any], evidence: dict[str, Any]) -> ProductCopyContext:
    product_name = str(understanding.get("product_name") or _product_from_evidence(evidence) or "product")
    normalized_type = str(understanding.get("normalized_product_type") or understanding.get("normalized_product_candidate") or "").strip() or None
    broad_category = str(understanding.get("broad_category") or "other")
    category_path = list(understanding.get("category_path") or [broad_category])
    territory = _message_territory_for_product(product_name, normalized_type, broad_category, evidence)
    language_policy = _dynamic_language_policy(product_name, normalized_type, broad_category, evidence)
    interaction_plan = _interaction_copy_plan(evidence)
    presence_plan = _minimal_copy_presence_plan(evidence, broad_category, interaction_plan)
    vocabulary = _vocabulary_for_product(product_name, normalized_type, broad_category)
    return ProductCopyContext(
        product_name=product_name,
        normalized_product_type=normalized_type,
        broad_category=broad_category,
        category_path=category_path,
        message_territories=[territory],
        sensory_vocabulary=vocabulary["sensory"],
        emotional_vocabulary=vocabulary["emotional"],
        functional_vocabulary=vocabulary["functional"],
        contextual_vocabulary=vocabulary["contextual"],
        product_entities=[product_name, *(category_path[-1:] if category_path else [])],
        adjacent_entities=vocabulary["adjacent"],
        excluded_territories=_excluded_territories(evidence, broad_category),
        customer_moments=vocabulary["moments"],
        language_policy=language_policy,
        copy_presence_plan=presence_plan,
        interaction_plan=interaction_plan,
        supported_claims=_supported_claims(evidence),
        unsupported_claims=list(understanding.get("unsupported_claim_categories") or UNSUPPORTED_CLAIM_CATEGORIES),
        confidence=float(understanding.get("confidence") or 0.75),
    )


def _message_territory_for_product(product_name: str, normalized_type: str | None, broad_category: str, evidence: dict[str, Any]) -> MessageTerritory:
    slug = normalized_type or normalize_slug(product_name) or "product"
    if broad_category == "food_and_beverage":
        label = "Warm product moment" if "jjigae" in slug else "Quiet taste moment"
        territory_id = "warm_meal_moment" if "jjigae" in slug else "minimal_cafe_moment"
    elif broad_category == "beauty_and_personal_care":
        label = "Calm daily routine"
        territory_id = "calm_daily_routine"
    elif broad_category == "fashion_and_lifestyle":
        label = "Seasonal style moment"
        territory_id = "seasonal_style_moment"
    else:
        label = "Simple product presence"
        territory_id = "simple_product_presence"
    return MessageTerritory(
        territory_id=territory_id,
        label=label,
        rationale="Derived from ProductUnderstanding category and verified product evidence.",
        supporting_evidence_keys=[item.get("evidence_id") for item in evidence.get("explicit_user_facts", []) if item.get("evidence_id")],
        suitability_score=0.82,
        visual_fit_score=0.76,
        risk_level="low",
    )


def _dynamic_language_policy(product_name: str, normalized_type: str | None, broad_category: str, evidence: dict[str, Any]) -> DynamicLanguagePolicy:
    text = " ".join([product_name, evidence.get("user_text") or "", normalized_type or ""]).lower()
    korean_local = bool(any("\uac00" <= ch <= "\ud7a3" for ch in product_name)) or any(token in text for token in ("jjigae", "kimchi", "korean"))
    if korean_local:
        return DynamicLanguagePolicy(
            primary_language="korean",
            headline_language="korean",
            supporting_copy_language="korean",
            english_headline_allowed=False,
            bilingual_allowed=False,
            romanization_allowed=False,
            rationale="Korean local food/product context should preserve Korean headline by default.",
            confidence=0.9,
        )
    if broad_category in {"beauty_and_personal_care", "fashion_and_lifestyle"}:
        return DynamicLanguagePolicy(
            primary_language="mixed",
            headline_language="korean",
            supporting_copy_language="korean",
            english_headline_allowed=True,
            bilingual_allowed=True,
            romanization_allowed=True,
            rationale="Editorial beauty/fashion copy may allow restrained bilingual naming when supported by context.",
            confidence=0.76,
        )
    return DynamicLanguagePolicy(rationale="Default Korean-first visual advertising policy.", confidence=0.78)


def _interaction_copy_plan(evidence: dict[str, Any]) -> InteractionCopyPlan:
    verified = " ".join(str(item.get("key") or "") + " " + str(item.get("value") or "") for item in evidence.get("explicit_user_facts", []))
    has_destination = any(token in verified.lower() for token in ("url", "phone", "reservation", "order", "qr", "예약", "주문", "전화"))
    return InteractionCopyPlan(
        interaction_mode="offline_with_action" if has_destination else "non_interactive_image",
        action_cta_allowed=has_destination,
        selected_role="embedded_action_cta" if has_destination else "closing_copy",
        action_destination_verified=has_destination,
        rationale=["Action CTA requires verified destination." if not has_destination else "Verified action destination is present."],
    )


def _minimal_copy_presence_plan(evidence: dict[str, Any], broad_category: str, interaction_plan: InteractionCopyPlan) -> MinimalCopyPresencePlan:
    has_promo = any(str(item.get("key") or "") in {"price", "promotion_detail"} for item in evidence.get("explicit_user_facts", []))
    image_only_possible = evidence.get("input_mode") == "image_only" and _has_product_visual_signal(evidence.get("visual_observations") or []) and not has_promo
    if image_only_possible:
        return MinimalCopyPresencePlan(mode="image_only", allowed_roles=[], max_text_blocks=0, max_total_characters=0, max_text_area_ratio=0.0, no_text_allowed=True, rationale=["Product image can carry the message without extra copy."])
    if has_promo or interaction_plan.action_cta_allowed:
        return MinimalCopyPresencePlan(mode="headline_plus_support", allowed_roles=["headline", "supporting_copy"], max_text_blocks=2, max_total_characters=64, max_text_area_ratio=0.12, no_text_allowed=False, rationale=["Verified promotional/action context benefits from one support line."])
    return MinimalCopyPresencePlan(mode="headline_only", allowed_roles=["headline"], max_text_blocks=1, max_total_characters=24, max_text_area_ratio=0.08, no_text_allowed=True, rationale=["Visual-first creative; one grounded headline is enough."])


def _vocabulary_for_product(product_name: str, normalized_type: str | None, broad_category: str) -> dict[str, list[str]]:
    slug = normalized_type or normalize_slug(product_name) or ""
    if "jjigae" in slug:
        return {"sensory": ["구수한", "따뜻한", "깊은"], "emotional": ["편안한", "익숙한"], "functional": ["한 그릇", "식사"], "contextual": ["오늘의 식탁", "저녁 한 끼"], "adjacent": ["밥", "상차림"], "moments": ["warm_meal_moment", "familiar_table"]}
    if "strawberry" in slug or "latte" in slug or "딸기" in product_name:
        return {"sensory": ["부드러운", "달콤한", "산뜻한"], "emotional": ["화사한", "가벼운"], "functional": ["한 잔", "신메뉴"], "contextual": ["카페 시간"], "adjacent": ["딸기", "우유"], "moments": ["quiet_cafe_pause"]}
    if broad_category == "food_and_beverage":
        return {"sensory": ["부드러운", "산뜻한"], "emotional": ["조용한", "달콤한"], "functional": ["메뉴"], "contextual": ["카페 시간"], "adjacent": ["디저트"], "moments": ["quiet_dessert_pause"]}
    if broad_category == "beauty_and_personal_care":
        return {"sensory": ["가벼운", "맑은"], "emotional": ["차분한", "깨끗한"], "functional": ["루틴", "케어"], "contextual": ["매일의 루틴"], "adjacent": ["피부", "텍스처"], "moments": ["calm_daily_routine"]}
    return {"sensory": [], "emotional": ["담백한"], "functional": [], "contextual": ["일상의 장면"], "adjacent": [], "moments": ["simple_product_presence"]}


def _excluded_territories(evidence: dict[str, Any], broad_category: str) -> list[str]:
    excluded = ["generic_action_cta", "discount_without_evidence", "price_without_evidence"]
    if broad_category == "beauty_and_personal_care":
        excluded.extend(["medical_effect", "guaranteed_result"])
    return excluded


def _supported_claims(evidence: dict[str, Any]) -> list[str]:
    return [str(item.get("key")) for item in evidence.get("explicit_user_facts", []) if item.get("key")]


def _product_from_evidence(evidence: dict[str, Any]) -> str | None:
    mentions = evidence.get("explicit_product_mentions") or []
    if mentions:
        return str(mentions[0])
    for item in [*(evidence.get("explicit_user_facts") or []), *(evidence.get("visual_observations") or [])]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").lower()
        value = item.get("normalized_value") or item.get("value")
        text = str(value or "").lower()
        if not text:
            continue
        if key in {"product_name", "product_identity", "product"}:
            return str(value)
    return None


def _has_product_visual_signal(observations: list[dict[str, Any]]) -> bool:
    for item in observations:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").lower()
        text = " ".join(str(item.get(field) or "") for field in ("value", "text", "product", "normalized_value")).strip()
        confidence = float(item.get("confidence") or 0.0)
        if confidence >= 0.7 and (key in {"product", "product_identity", "visual_product_candidate"} or len(text) >= 12):
            return True
    return False
