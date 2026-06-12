"""Build open-domain ProductUnderstanding from canonical input evidence."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.product_understanding_policy import normalize_slug, validate_product_understanding
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def product_understanding_node(state: dict[str, Any]) -> dict[str, Any]:
    raw_bundle = state.get("input_evidence_bundle")
    if not raw_bundle:
        return {"product_understanding": None, "product_understanding_status": "failed", "error_message": "input_evidence_bundle missing"}
    try:
        bundle = InputEvidenceBundle(**raw_bundle)
        if state.get("product_understanding_llm_response"):
            result = validate_product_understanding(state["product_understanding_llm_response"], bundle)
        else:
            from orchestrator.app.llm.product_understanding_service import generate_product_understanding

            result = generate_product_understanding(bundle, state=state)
    except Exception as exc:
        return {
            "product_understanding": None,
            "product_understanding_status": "failed",
            "product_understanding_confidence": 0.0,
            "product_understanding_provider_metadata": {},
            "error_message": str(exc)[:500],
        }
    status = "manual_review" if result.manual_review_required else "clarification_required" if result.clarification_required else "completed"
    return {
        "product_understanding": result.model_dump(),
        "product_understanding_status": status,
        "product_understanding_confidence": result.confidence,
        "product_understanding_provider_metadata": result.provider_metadata,
    }


def build_minimal_product_understanding(bundle: InputEvidenceBundle) -> ProductUnderstanding:
    product_name, evidence_ids = _product_identity(bundle)
    category = _broad_category_from_bundle(bundle)
    normalized_type = normalize_slug(product_name) if product_name else None
    category_path = [category]
    if normalized_type:
        category_path.append(normalized_type)
    confidence = 0.75 if evidence_ids else 0.45
    return ProductUnderstanding(
        product_name=product_name or "unknown product",
        normalized_product_type=normalized_type,
        broad_category=category,
        category_path=category_path,
        verified_facts=[item for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence if item.evidence_id in evidence_ids],
        visual_observations=[item for item in bundle.visual_observations if item.evidence_id in evidence_ids],
        permissible_inferences=[item for item in bundle.creative_inferences],
        unknown_fields=list(bundle.unknown_fields),
        unsupported_claim_categories=_unsupported_claim_categories(bundle),
        product_name_evidence_ids=evidence_ids,
        confidence_by_field={"product_name": confidence, "category_path": 0.55},
        confidence=confidence,
        clarification_required=not bool(product_name),
        manual_review_required=bundle.manual_review_required,
        provider_metadata={"provider": "deterministic", "fallback_used": True},
    )


def _product_identity(bundle: InputEvidenceBundle) -> tuple[str | None, list[str]]:
    if bundle.explicit_product_mentions:
        mention = bundle.explicit_product_mentions[0]
        ids = [item.evidence_id for item in bundle.explicit_user_facts if (item.normalized_value or item.value) == mention]
        return mention, ids
    for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence:
        if item.key in {"product_name", "item_or_service", "service_name"} and item.confidence >= 0.45:
            return item.normalized_value or item.value, [item.evidence_id]
    visual_candidates = [item for item in bundle.visual_observations if item.confidence >= 0.70 and item.usable_for_copy]
    if visual_candidates:
        item = visual_candidates[0]
        return item.normalized_value or item.value, [item.evidence_id]
    return None, []


def _broad_category_from_bundle(bundle: InputEvidenceBundle) -> str:
    for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence:
        if item.key in {"broad_category", "business_context"}:
            slug = normalize_slug(item.normalized_value or item.value)
            if slug in {
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
            }:
                return slug
    return "other"


def _unsupported_claim_categories(bundle: InputEvidenceBundle) -> list[str]:
    claims = {"price", "discount", "promotion_period", "scarcity", "inventory", "social_proof", "review_count", "ranking", "ingredient", "origin", "manufacturing_method", "certification", "medical_effect", "health_effect", "beauty_effect", "performance_guarantee", "safety_claim", "environmental_claim", "numeric_claim", "comparative_superiority", "delivery_condition", "warranty"}
    verified = {item.key for item in bundle.explicit_user_facts + bundle.asset_metadata_evidence + bundle.brand_profile_evidence + bundle.reference_evidence}
    return sorted(claim for claim in claims if claim not in verified)
