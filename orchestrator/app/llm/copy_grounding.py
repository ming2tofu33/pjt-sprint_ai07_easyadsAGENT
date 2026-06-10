"""Deterministic copy grounding checks."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyMessageStrategy, MarketingContext


class CopyGroundingResult(BaseModel):
    grounded: bool
    required_terms_found: list[str] = Field(default_factory=list)
    wrong_domain_terms: list[str] = Field(default_factory=list)
    unsupported_entities: list[str] = Field(default_factory=list)
    product_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    business_relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


DOMAIN_TERMS: dict[str, list[str]] = {
    "consumer_electronics": ["스마트폰", "스마트 워치", "배터리", "칩셋", "디스플레이", "카메라", "성능", "기술", "영상", "ai"],
    "food_beverage": ["메뉴", "맛", "음료", "디저트", "식사", "고기", "구이", "숯불", "한상", "라떼", "마카롱"],
    "beauty": ["네일", "헤어", "컬러", "스파", "피부", "손끝", "디자인", "케어"],
    "fitness_health": ["운동", "코칭", "헬스", "건강", "체력", "루틴"],
    "education": ["수업", "학습", "상담", "클래스", "강의"],
    "automotive": ["차량", "디테일링", "세차", "광택", "코팅"],
    "photography": ["촬영", "사진", "프로필", "스튜디오", "렌즈"],
    "flower": ["꽃", "꽃다발", "부케", "플라워"],
}

BUSINESS_DOMAIN: dict[str, str] = {
    "macaron": "food_beverage",
    "cafe": "food_beverage",
    "restaurant_bbq": "food_beverage",
    "restaurant": "food_beverage",
    "beauty_nail": "beauty",
    "beauty_hair": "beauty",
    "beauty_skincare": "beauty",
    "beauty_spa": "beauty",
    "fitness": "fitness_health",
    "education": "education",
    "car_detailing": "automotive",
    "photo_studio": "photography",
    "flower": "flower",
}

GENERIC_ABSTRACT_TERMS = ["소중한 순간", "감동", "일상", "꿈", "미래", "특별한 경험"]


def evaluate_copy_grounding(
    candidate: CopyCandidate,
    *,
    context: MarketingContext | None = None,
    strategy: CopyMessageStrategy | None = None,
) -> CopyGroundingResult:
    context = context or MarketingContext()
    text = _normalize(" ".join(filter(None, [candidate.headline, candidate.subcopy, candidate.cta])))
    anchors = build_context_anchors(context, strategy)
    required_found = [term for term in anchors if _normalize(term) and _normalize(term) in text]
    anchor_text = _normalize(" ".join(anchors))
    wrong_terms = [term for term in find_wrong_domain_terms(text, context.business_type) if _normalize(term) not in anchor_text]
    unsupported = [term for term in GENERIC_ABSTRACT_TERMS if term in text and not required_found]
    product_score = min(1.0, len(required_found) / max(1, min(2, len(anchors))))
    business_score = 1.0 if not wrong_terms else 0.0
    reasons: list[str] = []
    if not required_found:
        reasons.append("missing_product_or_service_anchor")
    if wrong_terms:
        reasons.append("wrong_domain_terms_detected")
    if unsupported:
        reasons.append("generic_unsupported_entities")
    grounded = bool(required_found) and not wrong_terms and product_score >= 0.5
    return CopyGroundingResult(
        grounded=grounded,
        required_terms_found=required_found,
        wrong_domain_terms=wrong_terms,
        unsupported_entities=unsupported,
        product_relevance_score=round(product_score, 3),
        business_relevance_score=business_score,
        reasons=reasons,
    )


def build_context_anchors(context: MarketingContext, strategy: CopyMessageStrategy | None = None) -> list[str]:
    raw: list[Any] = [
        context.item_or_service,
        context.business_type,
        context.usp,
        context.brand_name,
        context.promotion_goal,
        strategy.primary_value if strategy else None,
        strategy.proof_or_detail if strategy else None,
        *(strategy.supported_facts if strategy else []),
    ]
    anchors: list[str] = []
    for item in raw:
        if isinstance(item, list):
            anchors.extend(str(value) for value in item if value)
        elif item:
            anchors.extend(split_anchor_terms(str(item)))
    domain = BUSINESS_DOMAIN.get(str(context.business_type or "").lower())
    if domain:
        anchors.extend(DOMAIN_TERMS.get(domain, [])[:6])
    return sorted(set(term for term in anchors if len(term) >= 2))


def find_wrong_domain_terms(text: str, business_type: str | None) -> list[str]:
    expected = BUSINESS_DOMAIN.get(str(business_type or "").lower())
    wrong: list[str] = []
    for domain, terms in DOMAIN_TERMS.items():
        if domain == expected:
            continue
        for term in terms:
            if _normalize(term) in text:
                wrong.append(term)
    return sorted(set(wrong))


def split_anchor_terms(value: str) -> list[str]:
    parts = re.split(r"[\s,/\-|·]+", value)
    return [part.strip() for part in parts if len(part.strip()) >= 2]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()
