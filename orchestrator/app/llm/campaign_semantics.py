"""Shared campaign semantics helpers."""

from __future__ import annotations

from typing import Literal

from orchestrator.app.schemas.campaign_context import normalize_optional_text


CampaignSubjectRequirement = Literal["business", "product", "menu_or_product", "service"] | None
CampaignIntentFamily = Literal["business", "launch", "product", "service", "seasonal", "recruitment", "other"] | None


# Legacy inputs may still send grand_opening, but normalization collapses it to
# the canonical store_opening intent.
_CAMPAIGN_INTENT_LABELS = {
    "brand_awareness": "브랜드 인지도",
    "business_introduction": "매장 소개",
    "discount_event": "할인 이벤트",
    "grand_opening": "그랜드 오픈 홍보",
    "local_business_promotion": "매장 홍보",
    "new_menu_launch": "신메뉴 출시",
    "new_product_launch": "신상품 출시",
    "organization_promotion": "기관 홍보",
    "product_promotion": "상품 홍보",
    "reservation_cta": "예약/방문 유도",
    "review_event": "리뷰 이벤트",
    "seasonal_campaign": "시즌 한정 홍보",
    "seasonal_limited": "시즌 한정 홍보",
    "service_launch": "신규 서비스 시작",
    "service_promotion": "서비스 홍보",
    "store_opening": "신규 오픈 홍보",
    "student_recruitment": "수강생 모집",
}

_NORMALIZED_ALIASES = {
    "brand_awareness": "brand_awareness",
    "business_introduction": "business_introduction",
    "discount_event": "discount_event",
    "grand_opening": "store_opening",
    "local_business_promotion": "local_business_promotion",
    "new_launch": "new_launch",
    "new_menu": "new_menu_launch",
    "new_menu_launch": "new_menu_launch",
    "new_product": "new_product_launch",
    "new_product_launch": "new_product_launch",
    "organization_promotion": "organization_promotion",
    "product_promotion": "product_promotion",
    "reservation": "reservation_cta",
    "reservation_cta": "reservation_cta",
    "retention": "retention",
    "review_event": "review_event",
    "seasonal": "seasonal_limited",
    "seasonal_campaign": "seasonal_limited",
    "seasonal_limited": "seasonal_limited",
    "service_launch": "service_launch",
    "service_promotion": "service_promotion",
    "store_opening": "store_opening",
    "student_recruitment": "student_recruitment",
}

_BUSINESS_LEVEL_INTENTS = frozenset(
    {
        "brand_awareness",
        "business_introduction",
        "local_business_promotion",
        "organization_promotion",
        "store_opening",
        "student_recruitment",
    }
)
_PRODUCT_LEVEL_INTENTS = frozenset(
    {
        "discount_event",
        "new_menu_launch",
        "new_product_launch",
        "product_promotion",
        "reservation_cta",
        "review_event",
        "seasonal_limited",
    }
)
_SERVICE_LEVEL_INTENTS = frozenset({"service_launch", "service_promotion"})
_CANONICAL_INTENTS = _BUSINESS_LEVEL_INTENTS | _PRODUCT_LEVEL_INTENTS | _SERVICE_LEVEL_INTENTS
_BUSINESS_SUBJECT_TYPES = frozenset({"brand", "business", "venue"})
_PRODUCT_SUBJECT_TYPES = frozenset({"menu", "product"})
_SERVICE_SUBJECT_TYPES = frozenset({"service"})


def campaign_intent_label(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if not normalized:
        return None
    return _CAMPAIGN_INTENT_LABELS.get(normalized, normalized)


def normalize_campaign_intent(
    value: str | None,
    *,
    advertised_subject_type: str | None = None,
    campaign_status: str | None = None,
) -> str | None:
    raw_value = normalize_optional_text(value)
    normalized_value = _NORMALIZED_ALIASES.get(raw_value or "", raw_value or "")
    normalized_status = _NORMALIZED_ALIASES.get(normalize_optional_text(campaign_status) or "", normalize_optional_text(campaign_status) or "")
    subject_type = _normalized_subject_type(advertised_subject_type)

    if raw_value in {"new_menu_launch", "new_product_launch", "service_launch"}:
        return normalized_value
    if raw_value == "store_opening":
        return "store_opening" if subject_type in _BUSINESS_SUBJECT_TYPES or subject_type is None else None

    launch_signal = normalized_status or normalized_value
    if launch_signal == "new_menu_launch":
        return "new_menu_launch"
    if launch_signal in {"new_product_launch", "new_launch"}:
        if subject_type in _SERVICE_SUBJECT_TYPES:
            return "service_launch"
        if subject_type in _PRODUCT_SUBJECT_TYPES:
            return "new_product_launch"
        return None
    if launch_signal == "store_opening":
        return "store_opening" if subject_type in _BUSINESS_SUBJECT_TYPES else None

    if normalized_value in _CANONICAL_INTENTS:
        return normalized_value
    if normalized_value == "retention":
        return "retention"
    return normalized_value or None


def campaign_intent_subject_requirement(value: str | None) -> CampaignSubjectRequirement:
    normalized = normalize_optional_text(value)
    if normalized == "store_opening":
        return "business"
    if normalized == "new_product_launch":
        return "product"
    if normalized == "new_menu_launch":
        return "menu_or_product"
    if normalized == "service_launch":
        return "service"
    return None


def campaign_intent_family(value: str | None) -> CampaignIntentFamily:
    normalized = normalize_optional_text(value)
    if not normalized:
        return None
    if normalized in _BUSINESS_LEVEL_INTENTS:
        return "business"
    if normalized in {"new_product_launch", "new_menu_launch", "service_launch"}:
        return "launch"
    if normalized in {"discount_event", "product_promotion", "reservation_cta", "review_event"}:
        return "product"
    if normalized in {"service_promotion"}:
        return "service"
    if normalized in {"seasonal_limited"}:
        return "seasonal"
    return "other"


def project_legacy_promotion_goal(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if not normalized:
        return None
    if normalized in {"brand_awareness", "discount_event", "new_launch", "product_promotion", "reservation_cta", "retention", "review_event", "seasonal_limited"}:
        return normalized
    return None


def campaign_roles_for_intent(value: str | None) -> frozenset[str]:
    normalized = normalize_optional_text(value)
    if normalized == "store_opening":
        return frozenset({"announcement"})
    if normalized in {"new_product_launch", "new_menu_launch"}:
        return frozenset({"promotion"})
    if normalized == "service_launch":
        return frozenset({"information"})
    if normalized == "brand_awareness":
        return frozenset({"brand_awareness"})
    if normalized in {"business_introduction", "organization_promotion"}:
        return frozenset({"information"})
    if normalized in {"discount_event", "local_business_promotion", "product_promotion", "reservation_cta", "review_event", "seasonal_limited", "service_promotion"}:
        return frozenset({"promotion"})
    return frozenset()


def is_business_level_campaign_intent(value: str | None) -> bool:
    normalized = normalize_optional_text(value)
    return bool(normalized and normalized in _BUSINESS_LEVEL_INTENTS)


def is_item_level_campaign_intent(value: str | None) -> bool:
    normalized = normalize_optional_text(value)
    return bool(normalized and normalized in (_PRODUCT_LEVEL_INTENTS | _SERVICE_LEVEL_INTENTS))


def _normalized_subject_type(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized in _BUSINESS_SUBJECT_TYPES | _PRODUCT_SUBJECT_TYPES | _SERVICE_SUBJECT_TYPES:
        return normalized
    return None
