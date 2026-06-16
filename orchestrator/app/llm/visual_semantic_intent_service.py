"""Grounded visual semantic intent generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from pydantic import BaseModel

from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.visual_semantic_intent import (
    SemanticIntentAttribution,
    VisualSemanticIntent,
    VisualSemanticIntentDraft,
    VisualSemanticIntentGenerationResult,
    semantic_token_key,
)
from orchestrator.app.schemas.creative_routing import unfreeze_json_value


class VisualSemanticIntentValidationError(ValueError):
    pass


class VisualSemanticIntentGroundingError(VisualSemanticIntentValidationError):
    pass


class VisualSemanticIntentIdentifierLeakError(VisualSemanticIntentValidationError):
    pass


class StructuredSemanticIntentGenerator(Protocol):
    async def generate_structured(
        self,
        *,
        system_instruction: str,
        input_payload: Mapping[str, Any],
        response_model: type[BaseModel],
    ) -> BaseModel:
        ...


@dataclass(frozen=True)
class VisualSemanticIntentValidationPolicy:
    reserved_internal_identifiers: frozenset[str] = frozenset()
    require_attributions: bool = True


@dataclass(frozen=True)
class SemanticGroundingSnapshot:
    required_fact_candidates: frozenset[str]
    permissible_semantic_candidates: frozenset[str]
    prohibited_element_candidates: frozenset[str]
    available_evidence_refs: frozenset[str]
    available_source_paths: frozenset[str]
    source_path_values: Mapping[str, Any]


SYSTEM_INSTRUCTION = (
    "Create open visual semantic intent from the provided projection only. "
    "Use meanings and evidence present in input. Product facts and prohibitions "
    "must not be overridden by business environment. Campaign and ad format may "
    "inform priorities, composition, and copy presence. Omit uncertain items or "
    "record ambiguity. Do not generate preset, template, strategy, provider, or "
    "engine identifiers. Attach source paths or evidence refs to semantic items. "
    "For required_visual_facts and prohibited_visual_elements, reuse exact tokens "
    "from grounding_contract without translation, synonym replacement, or spacing changes."
)


LIST_ATTRIBUTION_FIELDS = {
    "desired_moods",
    "desired_materials",
    "lighting_preferences",
    "composition_preferences",
    "required_visual_facts",
    "prohibited_visual_elements",
}
SCALAR_ATTRIBUTION_FIELDS = {
    "subject_priority",
    "environment_priority",
    "text_priority",
    "copy_presence_mode",
    "confidence",
}


def build_visual_semantic_input_projection(context: CreativeRoutingContext) -> dict[str, Any]:
    return {
        "domain": {
            "canonical_domain": context.domain.canonical_domain.value,
            "support_status": context.domain.support_status.value,
            "fallback_reason": context.domain.fallback_reason.value if context.domain.fallback_reason else None,
            "confidence": context.domain.confidence,
        },
        "business": {
            "venue_type": context.business.venue_type,
            "service_model": context.business.service_model,
            "business_tags": list(context.business.business_tags),
            "environment_tags": list(context.business.environment_tags),
            "confidence": context.business.confidence,
        },
        "product": {
            "product_name": context.product.product_name,
            "category_path": list(context.product.category_path),
            "confidence": context.product.confidence,
        },
        "product_visual": {
            "product_tags": list(context.product_visual.product_tags),
            "visible_attributes": list(context.product_visual.visible_attributes),
            "explicit_preparation_methods": list(context.product_visual.explicit_preparation_methods),
            "permissible_visual_inferences": list(context.product_visual.permissible_visual_inferences),
            "prohibited_visual_inferences": list(context.product_visual.prohibited_visual_inferences),
            "confidence": context.product_visual.confidence,
        },
        "campaign": {
            "campaign_intent": context.campaign.campaign_intent,
            "campaign_status": context.campaign.campaign_status,
            "promotion_goal": context.campaign.promotion_goal,
            "desired_positioning": list(context.campaign.desired_positioning),
            "confidence": context.campaign.confidence,
        },
        "ad_format": {
            "ad_format": context.ad_format.ad_format,
            "platform": context.ad_format.platform,
            "aspect_ratio": context.ad_format.aspect_ratio,
            "width": context.ad_format.width,
            "height": context.ad_format.height,
            "information_density": context.ad_format.information_density,
            "visual_priority": context.ad_format.visual_priority,
            "output_strategy": context.ad_format.output_strategy,
        },
        "visual_observations": [
            {
                "evidence_id": item.evidence_id,
                "key": item.key,
                "value": item.normalized_value or item.value,
                "confidence": item.confidence,
            }
            for item in context.visual_observations
        ],
        "reference_style_profile": unfreeze_json_value(context.reference_style_profile),
        "ambiguity_flags": list(context.ambiguity_flags),
        "input_conflicts": [
            {
                "conflict_id": item.conflict_id,
                "field": item.field,
                "conflict_type": item.conflict_type,
                "severity": item.severity,
                "recommended_resolution": item.recommended_resolution,
            }
            for item in context.input_conflicts
        ],
    }


def build_semantic_grounding_snapshot(context: CreativeRoutingContext, projection: Mapping[str, Any]) -> SemanticGroundingSnapshot:
    required = {
        context.product.product_name,
        *context.product.category_path,
        *[item.normalized_value or item.value for item in context.product.verified_facts],
        *[item.normalized_value or item.value for item in context.product.visual_observations],
        *context.product_visual.product_tags,
        *context.product_visual.visible_attributes,
        *context.product_visual.explicit_preparation_methods,
        *[item.normalized_value or item.value for item in context.visual_observations],
    }
    permissible = set(context.product_visual.permissible_visual_inferences) | {
        item.normalized_value or item.value for item in context.product.permissible_inferences
    }
    prohibited = set(context.product_visual.prohibited_visual_inferences)
    evidence_refs = {
        *context.domain.evidence_refs,
        *context.business.evidence_refs,
        *context.product.product_name_evidence_ids,
        *context.product_visual.evidence_refs,
        *context.campaign.evidence_refs,
        *[item.evidence_id for item in context.product.verified_facts],
        *[item.evidence_id for item in context.product.visual_observations],
        *[item.evidence_id for item in context.product.permissible_inferences],
        *[item.evidence_id for item in context.visual_observations],
    }
    source_path_values = _json_leaf_values(projection)
    return SemanticGroundingSnapshot(
        required_fact_candidates=frozenset(_nonempty_keys(required)),
        permissible_semantic_candidates=frozenset(_nonempty_keys(permissible)),
        prohibited_element_candidates=frozenset(_nonempty_keys(prohibited)),
        available_evidence_refs=frozenset(ref for ref in evidence_refs if ref),
        available_source_paths=frozenset(source_path_values),
        source_path_values=source_path_values,
    )


async def generate_visual_semantic_intent(
    context: CreativeRoutingContext,
    *,
    generator: StructuredSemanticIntentGenerator,
    validation_policy: VisualSemanticIntentValidationPolicy | None = None,
) -> VisualSemanticIntentGenerationResult:
    if not isinstance(context, CreativeRoutingContext):
        raise TypeError("context must be CreativeRoutingContext")
    policy = validation_policy or VisualSemanticIntentValidationPolicy()
    projection = build_visual_semantic_input_projection(context)
    snapshot = build_semantic_grounding_snapshot(context, projection)
    generator_payload = {
        "context": projection,
        "grounding_contract": {
            "required_fact_candidates": sorted(snapshot.required_fact_candidates),
            "permissible_semantic_candidates": sorted(snapshot.permissible_semantic_candidates),
            "prohibited_element_candidates": sorted(snapshot.prohibited_element_candidates),
            "available_evidence_refs": sorted(snapshot.available_evidence_refs),
            "available_source_paths": sorted(snapshot.available_source_paths),
        },
    }
    response = await generator.generate_structured(
        system_instruction=SYSTEM_INSTRUCTION,
        input_payload=generator_payload,
        response_model=VisualSemanticIntentDraft,
    )
    draft = response if isinstance(response, VisualSemanticIntentDraft) else VisualSemanticIntentDraft.model_validate(response)
    _validate_draft(draft, snapshot, policy)
    projection_hash = hashlib.sha256(json.dumps(projection, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    merged_ambiguity_flags = _stable_string_merge([*context.ambiguity_flags, *draft.ambiguity_flags])
    return VisualSemanticIntentGenerationResult(
        intent=draft.intent,
        attributions=draft.attributions,
        ambiguity_flags=merged_ambiguity_flags,
        input_projection_hash=projection_hash,
        generator_id=getattr(generator, "generator_id", None),
    )


def _validate_draft(
    draft: VisualSemanticIntentDraft,
    snapshot: SemanticGroundingSnapshot,
    policy: VisualSemanticIntentValidationPolicy,
) -> None:
    _validate_grounded_items(draft.intent.required_visual_facts, snapshot.required_fact_candidates, "required_visual_facts")
    _validate_grounded_items(draft.intent.prohibited_visual_elements, snapshot.prohibited_element_candidates, "prohibited_visual_elements")
    _validate_reserved_identifiers(draft, policy)
    _validate_attributions(draft.intent, draft.attributions, snapshot, policy)


def _validate_grounded_items(values: list[str], candidates: frozenset[str], field_name: str) -> None:
    missing = [item for item in values if semantic_token_key(item) not in candidates]
    if missing:
        raise VisualSemanticIntentGroundingError(f"ungrounded {field_name}: {missing[0]}")


def _validate_reserved_identifiers(draft: VisualSemanticIntentDraft, policy: VisualSemanticIntentValidationPolicy) -> None:
    reserved = {semantic_token_key(item) for item in policy.reserved_internal_identifiers}
    if not reserved:
        return
    values = [
        *_semantic_values(draft.intent),
        *draft.ambiguity_flags,
        *[item.item_value for item in draft.attributions if item.item_value],
    ]
    for value in values:
        if semantic_token_key(value) in reserved:
            raise VisualSemanticIntentIdentifierLeakError(f"reserved internal identifier leaked: {value}")


def _validate_attributions(
    intent: VisualSemanticIntent,
    attributions: list[SemanticIntentAttribution],
    snapshot: SemanticGroundingSnapshot,
    policy: VisualSemanticIntentValidationPolicy,
) -> None:
    for attribution in attributions:
        if attribution.field_name not in VisualSemanticIntent.model_fields:
            raise VisualSemanticIntentValidationError(f"unknown attribution field_name: {attribution.field_name}")
        if not set(attribution.evidence_refs).issubset(snapshot.available_evidence_refs):
            raise VisualSemanticIntentValidationError("attribution contains unavailable evidence_ref")
        if not set(attribution.source_paths).issubset(snapshot.available_source_paths):
            raise VisualSemanticIntentValidationError("attribution contains unavailable source_path")
        if attribution.field_name in {"required_visual_facts", "prohibited_visual_elements"}:
            _validate_strong_fact_attribution(attribution, snapshot)
    if not policy.require_attributions:
        return
    indexed = {(item.field_name, item.item_value) for item in attributions}
    for field in LIST_ATTRIBUTION_FIELDS:
        for value in getattr(intent, field):
            if (field, value) not in indexed:
                raise VisualSemanticIntentValidationError(f"missing attribution for {field}: {value}")
    fields_with_attribution = {item.field_name for item in attributions}
    for field in SCALAR_ATTRIBUTION_FIELDS:
        if field not in fields_with_attribution:
            raise VisualSemanticIntentValidationError(f"missing attribution for {field}")


def _semantic_values(intent: VisualSemanticIntent) -> list[str]:
    values = [intent.copy_presence_mode]
    for field in LIST_ATTRIBUTION_FIELDS:
        values.extend(getattr(intent, field))
    return values


def _validate_strong_fact_attribution(
    attribution: SemanticIntentAttribution,
    snapshot: SemanticGroundingSnapshot,
) -> None:
    if not attribution.item_value:
        raise VisualSemanticIntentValidationError("required/prohibited attribution requires item_value")
    if attribution.is_derived:
        raise VisualSemanticIntentValidationError("required/prohibited attribution must not be derived")
    item_key = semantic_token_key(attribution.item_value)
    for path in attribution.source_paths:
        value = snapshot.source_path_values.get(path)
        if isinstance(value, str) and semantic_token_key(value) == item_key:
            return
    raise VisualSemanticIntentValidationError("required/prohibited attribution source_path must match item_value")


def _nonempty_keys(values: set[str | None]) -> set[str]:
    return {semantic_token_key(value) for value in values if isinstance(value, str) and value.strip()}


def _json_leaf_values(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            output.update(_json_leaf_values(child, f"{prefix}.{key}"))
        return output
    if isinstance(value, list):
        output: dict[str, Any] = {}
        for index, child in enumerate(value):
            output.update(_json_leaf_values(child, f"{prefix}[{index}]"))
        return output
    return {prefix: value}


def _stable_string_merge(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item or item in seen:
            continue
        output.append(item)
        seen.add(item)
    return output
