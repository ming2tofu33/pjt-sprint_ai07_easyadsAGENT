"""Normalize raw multimodal input into a canonical evidence bundle."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict, InputEvidenceBundle


DEFAULT_UNKNOWN_FIELDS = ["specific_variant", "brand_name", "price", "promotion_detail", "ingredients", "origin", "manufacturing_method"]
PRODUCT_CONTEXT_KEYS = ("item_or_service", "product_name", "service_name")


def input_evidence_normalizer_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        bundle = build_input_evidence_bundle(state)
    except Exception as exc:
        return {"input_evidence_bundle": None, "input_normalization_status": "failed", "clarification_required": False, "error_message": str(exc)[:500]}
    if bundle.manual_review_required:
        status = "manual_review"
    elif bundle.clarification_required:
        status = "clarification_required"
    else:
        status = "completed"
    return {
        "input_evidence_bundle": bundle.model_dump(),
        "input_normalization_status": status,
        "input_conflicts": [item.model_dump() for item in bundle.input_conflicts],
        "unresolved_questions": list(bundle.unresolved_questions),
        "clarification_required": bundle.clarification_required,
    }


def build_input_evidence_bundle(state: dict[str, Any]) -> InputEvidenceBundle:
    user_text = str(state.get("user_input") or "").strip() or None
    source_image_path = state.get("source_image_path")
    input_mode = _input_mode(user_text, source_image_path)
    product = _product_from_state(state, user_text=user_text)
    user_intent = resolve_user_intent(user_text, promotion_goal=state.get("promotion_goal") or _context_value(state, "promotion_goal"))
    facts: list[EvidenceItem] = []
    if user_text and product:
        facts.append(_fact("product_name", product, source_ref="user_input"))
    if user_text and _has_new_menu_intent(user_text):
        facts.append(_fact("launch_status", "new_menu", source_ref="user_input"))
    business_context = _context_value(state, "business_type")
    if user_text and business_context:
        facts.append(_fact("business_context", str(business_context), source_ref="context"))
    visual = _visual_observations_from_state(state)
    conflicts = _detect_conflicts(product if user_text else None, visual)
    fact_keys = {item.key for item in facts}
    unknown = [field for field in DEFAULT_UNKNOWN_FIELDS if field not in fact_keys]
    questions = _questions_for_unknowns(user_intent, unknown)
    return InputEvidenceBundle(
        input_mode=input_mode,
        user_text=user_text,
        user_intent=user_intent,
        placement=state.get("placement") or state.get("selected_ad_format") or (state.get("ad_format_spec") or {}).get("ad_format"),
        promotion_goal=state.get("promotion_goal") or _context_value(state, "promotion_goal"),
        source_asset_id=state.get("source_asset_id"),
        reference_asset_id=state.get("reference_asset_id"),
        source_image_sha256=state.get("source_image_sha256") or (_sha256_file(Path(source_image_path)) if source_image_path else None),
        source_provenance=state.get("source_provenance") or ("user_uploaded" if source_image_path else None),
        explicit_product_mentions=[product] if user_text and product else [],
        explicit_user_facts=facts,
        visual_observations=visual,
        input_conflicts=conflicts,
        unknown_fields=unknown,
        unresolved_questions=questions,
        clarification_required=bool(questions),
        manual_review_required=any(item.severity == "manual_review" for item in conflicts),
        overall_confidence=_overall_confidence(input_mode=input_mode, facts=facts, visual=visual, conflicts=conflicts),
        provider_metadata=state.get("input_evidence_provider_metadata") or {},
    )


def resolve_product_identity(bundle: InputEvidenceBundle) -> str | None:
    if bundle.explicit_product_mentions:
        return bundle.explicit_product_mentions[0]
    for item in bundle.asset_metadata_evidence:
        if item.key == "product_name":
            return item.normalized_value or item.value
    confident = [item for item in bundle.visual_observations if item.key == "product_identity" and item.confidence >= 0.7]
    return (confident[0].normalized_value or confident[0].value) if confident else None


def resolve_verified_fact(bundle: InputEvidenceBundle, key: str) -> str | None:
    for source in (bundle.explicit_user_facts, bundle.asset_metadata_evidence, bundle.brand_profile_evidence):
        for item in source:
            if item.key == key and item.evidence_class == "verified_fact":
                return item.normalized_value or item.value
    return None


def resolve_visual_attribute(bundle: InputEvidenceBundle, key: str) -> str | None:
    for item in bundle.visual_observations:
        if item.key == key and item.confidence >= 0.45:
            return item.normalized_value or item.value
    return None


def resolve_user_intent(text: str | None, promotion_goal: str | None = None) -> str | None:
    if promotion_goal:
        return str(promotion_goal)
    lowered = (text or "").lower()
    if _has_new_menu_intent(text):
        return "new_menu_promotion"
    if "홍보" in (text or "") or "promote" in lowered or "advertise" in lowered:
        return "product_promotion"
    return None


def resolve_placement(bundle: InputEvidenceBundle) -> str | None:
    return bundle.placement


def _input_mode(user_text: str | None, source_image_path: object) -> str:
    if user_text and source_image_path:
        return "text_and_image"
    if source_image_path:
        return "image_only"
    return "text_only"


def _product_from_state(state: dict[str, Any], *, user_text: str | None) -> str | None:
    for key in PRODUCT_CONTEXT_KEYS:
        value = _context_value(state, key) or state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    brief = state.get("current_brief") or {}
    if isinstance(brief, dict):
        for key in PRODUCT_CONTEXT_KEYS:
            value = brief.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    metadata = state.get("asset_metadata") or {}
    if isinstance(metadata, dict):
        value = metadata.get("product_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if user_text:
        return user_text.strip()
    return None


def _context_value(state: dict[str, Any], key: str) -> Any:
    context = state.get("context") or {}
    if hasattr(context, key):
        return getattr(context, key)
    if isinstance(context, dict):
        if key in context:
            return context[key]
        extra = context.get("extra")
        if isinstance(extra, dict):
            return extra.get(key)
    return None


def _has_new_menu_intent(text: str | None) -> bool:
    lowered = (text or "").lower()
    return "신메뉴" in (text or "") or "new menu" in lowered


def _fact(key: str, value: str, *, source_ref: str) -> EvidenceItem:
    return EvidenceItem(key=key, value=value, normalized_value=value, source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True, source_ref=source_ref)


def _visual_observations_from_state(state: dict[str, Any]) -> list[EvidenceItem]:
    raw = state.get("input_visual_observations") or []
    if not raw and state.get("vision_pipeline_results"):
        raw = (state.get("vision_pipeline_results") or [{}])[-1].get("visual_observations") or []
    items: list[EvidenceItem] = []
    for entry in raw:
        item = _visual_item(entry)
        if item:
            items.append(item)
    return items


def _visual_item(entry: object) -> EvidenceItem | None:
    if isinstance(entry, str):
        return EvidenceItem(key="visual_description", value=entry, source="image_vlm", evidence_class="visual_observation", confidence=0.5, usable_for_copy=True)
    if not isinstance(entry, dict):
        return None
    key = str(entry.get("key") or entry.get("kind") or "visual_description")
    value = str(entry.get("value") or entry.get("text") or entry.get("product") or "")
    if not value:
        return None
    confidence = float(entry.get("confidence") if entry.get("confidence") is not None else 0.0)
    existing_text = key == "existing_overlay_text" or _looks_like_existing_text(entry, value)
    return EvidenceItem(
        key="existing_overlay_text" if existing_text else key,
        value=value,
        normalized_value=str(entry.get("normalized_value") or value),
        source="image_vlm",
        evidence_class="visual_observation",
        confidence=max(0.0, min(1.0, confidence)),
        usable_for_copy=False if existing_text else key not in {"ingredients", "origin", "calorie", "health_effect"},
    )


def _looks_like_existing_text(entry: dict[str, Any], value: str) -> bool:
    label = " ".join(str(entry.get(key) or "") for key in ("key", "kind", "rationale", "text_type")).lower()
    return "text" in label or "cta" in label or "headline" in label or "korean text" in value.lower()


def _detect_conflicts(text_product: str | None, visual: list[EvidenceItem]) -> list[InputConflict]:
    visual_identity = next((item for item in visual if item.key in {"product_identity", "product"} and item.confidence >= 0.7), None)
    if not text_product or not visual_identity:
        return []
    if _norm(text_product) == _norm(visual_identity.normalized_value or visual_identity.value):
        return []
    return [InputConflict(field="product_identity", text_value=text_product, image_value=visual_identity.value, conflict_type="identity_mismatch", severity="manual_review", confidence=visual_identity.confidence, recommended_resolution="manual_review")]


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _overall_confidence(*, input_mode: str, facts: list[EvidenceItem], visual: list[EvidenceItem], conflicts: list[InputConflict]) -> float:
    identity = 1.0 if any(item.key == "product_name" for item in facts) else max([item.confidence for item in visual if item.key in {"product_identity", "product"}] or [0.0])
    source = 1.0 if facts else (0.8 if visual else 0.0)
    coverage = 1.0 if (facts or input_mode == "image_only") else 0.5
    visual_score = 1.0 if input_mode == "text_only" else (sum(item.confidence for item in visual) / max(1, len(visual)))
    penalty = 0.35 if conflicts else 0.0
    return max(0.0, min(1.0, identity * 0.4 + source * 0.25 + coverage * 0.2 + visual_score * 0.15 - penalty))


def _questions_for_unknowns(intent: str | None, unknown: list[str]) -> list[str]:
    if intent and "promotion" in intent and "price" in unknown:
        return []
    return []


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
