"""Deterministic validation and selection policy for minimal product copy."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.product_understanding_policy import normalize_slug
from orchestrator.app.schemas.product_copy_context import MinimalCopyCandidate, MinimalCopyPresencePlan, ProductCopyContext


GENERIC_CTA_TERMS = {
    "learn more",
    "discover more",
    "find out more",
    "shop now",
    "view menu",
    "menu",
    "meet",
    "discover",
    "지금 확인하기",
    "자세히 보기",
    "메뉴 보기",
    "지금 만나보세요",
    "지금 만나보기",
}


def build_minimal_copy_candidates(data: dict[str, Any], context: ProductCopyContext) -> list[MinimalCopyCandidate]:
    selected = sanitize_selected_copy(_normalize_selected_copy(data.get("selected_copy") or {}))
    headline = _minimal_headline(selected.get("headline"), context)
    support = _minimal_support(selected.get("subcopy"), context)
    closing = _minimal_closing(selected.get("closing_copy") or selected.get("cta"), context)
    territory = context.message_territories[0].territory_id if context.message_territories else None
    evidence_keys = [item for territory_item in context.message_territories for item in territory_item.supporting_evidence_keys]
    language = context.language_policy.headline_language

    candidates: list[MinimalCopyCandidate] = [
        MinimalCopyCandidate(candidate_id="variant_image_only", variant_type="image_only", territory_id=None, headline=None, supporting_copy=None, closing_copy=None, action_cta=None, language_mode=context.language_policy.primary_language, supporting_evidence_keys=[], text_block_count=0, estimated_text_area_ratio=0.0)
    ]
    if headline:
        candidates.append(MinimalCopyCandidate(candidate_id="variant_headline_only", variant_type="headline_only", territory_id=territory, headline=headline, language_mode=language, supporting_evidence_keys=evidence_keys, text_block_count=1, estimated_text_area_ratio=0.06))
    if headline and support:
        candidates.append(MinimalCopyCandidate(candidate_id="variant_headline_plus_support", variant_type="headline_plus_support", territory_id=territory, headline=headline, supporting_copy=support, language_mode=context.language_policy.primary_language, supporting_evidence_keys=evidence_keys, text_block_count=2, estimated_text_area_ratio=0.10))
    if headline and closing:
        candidates.append(MinimalCopyCandidate(candidate_id="variant_headline_plus_closing", variant_type="headline_plus_closing", territory_id=territory, headline=headline, closing_copy=closing, action_cta=None, language_mode=context.language_policy.primary_language, supporting_evidence_keys=evidence_keys, text_block_count=2, estimated_text_area_ratio=0.09))
    return [item for item in candidates if validate_minimal_copy_candidate(item)]


def validate_minimal_copy_candidate(candidate: MinimalCopyCandidate) -> bool:
    roles = [candidate.headline, candidate.supporting_copy, candidate.closing_copy, candidate.action_cta]
    non_empty = sum(1 for value in roles if str(value or "").strip())
    if candidate.variant_type == "image_only":
        return candidate.text_block_count == 0 and non_empty == 0
    if candidate.variant_type == "headline_only":
        return bool(candidate.headline) and candidate.text_block_count == 1 and non_empty == 1
    if candidate.variant_type == "headline_plus_support":
        return bool(candidate.headline and candidate.supporting_copy) and candidate.text_block_count == 2 and non_empty == 2
    if candidate.variant_type == "headline_plus_closing":
        return bool(candidate.headline and candidate.closing_copy) and candidate.text_block_count == 2 and non_empty == 2
    return False


def select_minimal_candidate_for_plan(plan: MinimalCopyPresencePlan, candidates: list[MinimalCopyCandidate]) -> MinimalCopyCandidate | None:
    preferred = {
        "image_only": "image_only",
        "brand_only": "headline_only",
        "headline_only": "headline_only",
        "headline_plus_support": "headline_plus_support",
        "headline_plus_closing": "headline_plus_closing",
    }.get(plan.mode)
    return next((item for item in candidates if item.variant_type == preferred), None) or next((item for item in candidates if item.variant_type == "headline_only"), None) or (candidates[0] if candidates else None)


def copy_from_minimal_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return sanitize_selected_copy(
        {
            "headline": candidate.get("headline"),
            "subcopy": candidate.get("supporting_copy") or candidate.get("closing_copy"),
            "cta": candidate.get("action_cta"),
            "closing_copy": candidate.get("closing_copy"),
            "variant_type": candidate.get("variant_type"),
            "candidate_id": candidate.get("candidate_id"),
        }
    )


def sanitize_selected_copy(selected: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(selected or {})
    cta = cleaned.get("cta")
    if is_generic_cta(cta):
        cleaned["cta"] = None
    return cleaned


def is_generic_cta(value: object) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return text in GENERIC_CTA_TERMS or any(text.startswith(f"{term} ") for term in GENERIC_CTA_TERMS if term.isascii())


def _normalize_selected_copy(selected: dict[str, Any]) -> dict[str, str | None]:
    def clean(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    return {
        "headline": clean(selected.get("headline") or selected.get("title") or selected.get("primary_text")),
        "subcopy": clean(selected.get("subcopy") or selected.get("supporting_copy") or selected.get("secondary_text") or selected.get("body") or selected.get("primary_text")),
        "cta": clean(selected.get("cta") or selected.get("call_to_action")),
        "closing_copy": clean(selected.get("closing_copy")),
    }


def _minimal_headline(value: str | None, context: ProductCopyContext) -> str:
    product = context.product_name
    if value and not is_generic_cta(value):
        return _truncate_copy(value, 24 if context.language_policy.headline_language == "korean" else 48)
    slug = context.normalized_product_type or normalize_slug(product) or ""
    joined_vocab = " ".join([*context.adjacent_entities, *context.sensory_vocabulary, product])
    if "jjigae" in slug:
        return "구수하게 끓여낸 한 그릇"
    if "strawberry" in slug or "latte" in slug or "딸기" in joined_vocab:
        if "우유" in joined_vocab or "milk" in joined_vocab.lower():
            return "딸기와 우유가 만난 부드러운 한 잔"
        return "새로 만나는 딸기라떼"
    if context.broad_category == "food_and_beverage":
        return f"{product}의 조용한 순간"
    if context.broad_category == "beauty_and_personal_care":
        return "차분하게 채우는 루틴"
    return product


def _minimal_support(value: str | None, context: ProductCopyContext) -> str | None:
    if value and not is_generic_cta(value):
        return _truncate_copy(value, 40)
    if context.copy_presence_plan.mode == "headline_plus_support":
        return "검증된 정보 안에서 담백하게 전합니다"
    return None


def _minimal_closing(value: str | None, context: ProductCopyContext) -> str | None:
    if value and not is_generic_cta(value):
        return _truncate_copy(value, 24)
    if context.interaction_plan.action_cta_allowed:
        return None
    if context.normalized_product_type and "jjigae" in context.normalized_product_type:
        return "오늘의 식탁에 구수함을"
    return "기억에 남는 한 장면"


def _truncate_copy(value: str, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip()
