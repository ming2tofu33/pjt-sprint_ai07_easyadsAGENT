"""Deterministic validation and confidence policy for product understanding."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding, UNSUPPORTED_CLAIM_CATEGORIES

_SNAKE_CASE_RE = re.compile(r"^(?=.*[a-z])[a-z0-9]+(?:_[a-z0-9]+)*$")
ROOT_ALIASES = {"food_beverage", "beauty_personal_care", "fashion_lifestyle", "home_living"}
REQUEST_INTENT_PATTERNS = [
    r"홍보(?:하고 싶어|해\s*줘|해주세요)",
    r"광고(?:하고 싶어|해\s*줘|해주세요)",
    r"소개(?:하고 싶어|해\s*줘|해주세요)",
    r"만들어\s*줘",
    r"제작해\s*줘",
    r"디자인해\s*줘",
    r"알리고 싶어",
    r"\bi want to promote\b",
    r"\bcreate an ad\b",
    r"\bmake an advertisement\b",
    r"\badvertise this\b",
    r"\bpromote this\b",
]
_UNICODE_SLUG_REPLACEMENTS = {
    "된장찌개": "doenjang jjigae",
    "김치찌개": "kimchi jjigae",
    "부대찌개": "budae jjigae",
    "찌개": "jjigae",
    "메뉴": "menu",
    "음식": "food",
    "식당": "restaurant",
    "카페": "cafe",
    "커피": "coffee",
    "라떼": "latte",
    "디저트": "dessert",
    "딸기": "strawberry",
    "세럼": "serum",
    "나이아신아마이드": "niacinamide",
}


def normalize_slug(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().lower()
    for source, replacement in _UNICODE_SLUG_REPLACEMENTS.items():
        text = text.replace(source, f" {replacement} ")
    slug = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return slug or None


def validate_product_understanding(
    result: ProductUnderstanding | dict[str, Any],
    bundle: InputEvidenceBundle | dict[str, Any],
) -> ProductUnderstanding:
    bundle_model = bundle if isinstance(bundle, InputEvidenceBundle) else InputEvidenceBundle(**bundle)
    model = result if isinstance(result, ProductUnderstanding) else ProductUnderstanding(**result)
    if len(model.category_path) == 1 and model.normalized_product_type:
        raise ValueError("category_path must include product hierarchy when product identity is known")
    if _contains_request_intent(model.product_name):
        raise ValueError("product_identity_contaminated")
    if any(item in ROOT_ALIASES for item in model.category_path[1:]):
        raise ValueError("category_path cannot contain root aliases below broad_category")
    _validate_verified_fact_provenance(model, bundle_model)
    _validate_visual_provenance(model, bundle_model)
    _validate_product_identity_conflict(model, bundle_model)
    confidence = calculate_product_understanding_confidence(model, bundle_model)
    return model.model_copy(
        update={
            "unknown_fields": sorted(set(model.unknown_fields)),
            "unsupported_claim_categories": unsupported_claim_categories_for_bundle(bundle_model),
            "campaign_intent": model.campaign_intent or bundle_model.campaign_intent,
            "desired_positioning": list(model.desired_positioning or bundle_model.desired_positioning),
            "confidence": confidence,
            "clarification_required": model.clarification_required or (0.45 <= confidence < 0.70),
            "manual_review_required": model.manual_review_required or confidence < 0.45,
        }
    )


def unsupported_claim_categories_for_bundle(bundle: InputEvidenceBundle) -> list[str]:
    verified_keys = {
        normalize_slug(item.key)
        for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence
    }
    allowed = {item for item in verified_keys if item in UNSUPPORTED_CLAIM_CATEGORIES}
    return sorted(set(UNSUPPORTED_CLAIM_CATEGORIES) - allowed)


def calculate_product_understanding_confidence(model: ProductUnderstanding, bundle: InputEvidenceBundle) -> float:
    identity_ids = set(model.product_name_evidence_ids)
    verified_ids = {item.evidence_id for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence}
    visual_ids = {item.evidence_id for item in bundle.visual_observations}
    identity_evidence_score = 1.0 if identity_ids & verified_ids else 0.78 if identity_ids & visual_ids else 0.55
    source_authority_score = 1.0 if identity_ids & verified_ids else 0.75 if identity_ids & visual_ids else 0.55
    category_consistency_score = 1.0 if model.category_path and model.category_path[0] == model.broad_category else 0.0
    field_completeness_score = sum(bool(value) for value in [model.product_name, model.broad_category, model.category_path, model.normalized_product_type]) / 4
    text_norm = _norm((bundle.explicit_product_mentions or [""])[0])
    visual_values = [_norm(item.normalized_value or item.value) for item in bundle.visual_observations if item.confidence >= 0.7]
    cross_source_agreement_score = 1.0 if text_norm and text_norm in visual_values else 0.7 if text_norm or visual_values else 0.5
    conflict_penalty = 0.25 if bundle.input_conflicts else 0.0
    return max(
        0.0,
        min(
            1.0,
            identity_evidence_score * 0.40
            + source_authority_score * 0.20
            + category_consistency_score * 0.15
            + field_completeness_score * 0.10
            + cross_source_agreement_score * 0.15
            - conflict_penalty,
        ),
    )


def _validate_verified_fact_provenance(model: ProductUnderstanding, bundle: InputEvidenceBundle) -> None:
    allowed = {item.evidence_id for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence}
    for item in model.verified_facts:
        if item.evidence_id not in allowed:
            raise ValueError("verified fact evidence_id not present in InputEvidenceBundle verified sources")


def _validate_visual_provenance(model: ProductUnderstanding, bundle: InputEvidenceBundle) -> None:
    allowed = {item.evidence_id for item in bundle.visual_observations + bundle.asset_metadata_evidence}
    for item in model.visual_observations:
        if item.evidence_id not in allowed:
            raise ValueError("visual observation evidence_id not present in InputEvidenceBundle visual sources")


def _validate_product_identity_conflict(model: ProductUnderstanding, bundle: InputEvidenceBundle) -> None:
    if any(conflict.field == "product_identity" and conflict.severity == "manual_review" for conflict in bundle.input_conflicts):
        raise ValueError("product identity conflict requires manual review")
    if model.normalized_product_type and not _SNAKE_CASE_RE.match(model.normalized_product_type):
        raise ValueError("normalized_product_type must be lowercase snake_case")


def _norm(value: str | None) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _contains_request_intent(value: str | None) -> bool:
    return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in REQUEST_INTENT_PATTERNS)
