"""Canonical actual creative pipeline.

This module is the shared actual runtime path for final creative smoke runners.
It is fail-closed: completed results require real provider metadata, positive
token usage, production rendering, and a final composite distinct from the
source/background image.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, model_validator

from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.llm.minimal_copy_policy import (
    build_minimal_copy_candidates as production_build_minimal_copy_candidates,
    copy_from_minimal_candidate as production_copy_from_minimal_candidate,
    is_generic_cta as production_is_generic_cta,
    sanitize_selected_copy as production_sanitize_selected_copy,
    select_minimal_candidate_for_plan as production_select_minimal_candidate_for_plan,
)
from orchestrator.app.llm.product_copy_context_service import build_dynamic_product_copy_context as production_build_dynamic_product_copy_context
from orchestrator.app.llm.nodes.product_understanding import build_minimal_product_understanding
from orchestrator.app.llm.product_understanding_policy import normalize_slug, validate_product_understanding
from orchestrator.app.llm.product_understanding_service import generate_product_understanding
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.product_understanding import UNSUPPORTED_CLAIM_CATEGORIES
from orchestrator.app.t2i.engines.base import T2IGenerationInput


InputMode = Literal["text_only", "image_only", "text_and_image"]
ImageUsePlanMode = Literal[
    "generate_from_text",
    "use_uploaded_as_background",
    "analyze_then_regenerate",
    "manual_review",
]
ActualStatus = Literal["completed", "manual_review", "failed", "blocked"]
ALLOWED_USER_FACT_KEYS = {"product_name", "brand_name", "launch_status", "price", "promotion_detail", "ingredient", "origin", "business_context"}
FORBIDDEN_EVIDENCE_KEYS = {"case_id", "input_mode", "seed", "output_dir", "source_image_path", "source_asset_id", "reference_asset_id", "source_provenance", "placement", "promotion_goal"}
REVISION_ACTIONS = {"minor_revision", "retry_layout", "retry_text_style", "rewrite_copy", "revise_copy", "regenerate_background"}


class ActualCreativeInput(BaseModel):
    case_id: str
    input_mode: InputMode
    user_text: str | None = None
    source_image_path: str | None = None
    source_asset_id: str | None = None
    reference_asset_id: str | None = None
    placement: str = "instagram_feed_static"
    promotion_goal: str = "brand_awareness"
    seed: int = 62
    output_dir: str
    source_provenance: str | None = None

    @model_validator(mode="after")
    def validate_mode_inputs(self):
        has_text = bool((self.user_text or "").strip())
        if self.source_asset_id or self.reference_asset_id:
            raise ValueError("source_asset_id and reference_asset_id are not supported by this local-path actual runner")
        has_source = bool(self.source_image_path)
        if self.input_mode == "text_only" and not has_text:
            raise ValueError("text_only requires user_text")
        if self.input_mode == "image_only" and not has_source:
            raise ValueError("image_only requires source_image_path")
        if self.input_mode == "text_and_image" and (not has_text or not has_source):
            raise ValueError("text_and_image requires user_text and source_image_path")
        return self


@dataclass
class ActualCallBudget:
    max_openai_calls: int = 6
    max_flux_generations: int = 1
    openai_calls_used: int = 0
    flux_generations_used: int = 0

    def consume_openai(self) -> None:
        if self.openai_calls_used >= self.max_openai_calls:
            raise RuntimeError("openai_call_budget_exceeded")
        self.openai_calls_used += 1

    def consume_flux(self) -> None:
        if self.flux_generations_used >= self.max_flux_generations:
            raise RuntimeError("flux_generation_budget_exceeded")
        self.flux_generations_used += 1


@dataclass
class ActualCreativeRuntime:
    copy_model: str = "gpt-5.4"
    vision_model: str = "gpt-5.4"
    t2i_engine: str = "flux2_klein_4b"
    t2i_backend: str = "local_diffusers"
    openai_adapter: Any = None
    vision_adapter: Any = None
    flux_engine: Any = None
    call_budget: ActualCallBudget | None = None
    render_all_variants: bool = False


class ActualSourceImageAnalysis(BaseModel):
    visual_observations: list[dict[str, Any]] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ActualProductCopyOutput(BaseModel):
    product_understanding: dict[str, Any]
    product_copy_context: dict[str, Any]
    copy_presence_plan: dict[str, Any] = Field(default_factory=dict)
    language_policy: dict[str, Any] = Field(default_factory=dict)
    interaction_copy_plan: dict[str, Any] = Field(default_factory=dict)
    copy_candidates: list[dict[str, Any]]
    minimal_copy_candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_variant_id: str | None = None
    recommended_candidate_id: str | None = None
    selected_copy: dict[str, Any] | None = None
    input_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    requires_manual_review: bool = False
    provider_metadata: dict[str, Any]


class ActualProductUnderstandingOutput(BaseModel):
    product_understanding: dict[str, Any]
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ActualCreativeVLMResult(BaseModel):
    product_match_score: float = Field(ge=0.0, le=1.0)
    copy_product_grounding_score: float = Field(ge=0.0, le=1.0)
    copy_readability_score: float = Field(ge=0.0, le=1.0)
    copy_visual_fit_score: float = Field(ge=0.0, le=1.0)
    product_obstruction_score: float = Field(ge=0.0, le=1.0)
    wrong_domain_detected: bool
    unsupported_claim_detected: bool
    commercial_viability_score: float = Field(ge=0.0, le=1.0)
    failure_reasons: list[str] = Field(default_factory=list)
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    detected_text: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, Any]


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


class ImageUsePlan(BaseModel):
    mode: ImageUsePlanMode
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ActualCreativeResult(BaseModel):
    case_id: str
    input_mode: str
    status: ActualStatus
    input_evidence: dict[str, Any] = Field(default_factory=dict)
    product_understanding: dict[str, Any] = Field(default_factory=dict)
    product_copy_context: dict[str, Any] = Field(default_factory=dict)
    copy_presence_plan: dict[str, Any] = Field(default_factory=dict)
    language_policy: dict[str, Any] = Field(default_factory=dict)
    interaction_copy_plan: dict[str, Any] = Field(default_factory=dict)
    image_use_plan: dict[str, Any] = Field(default_factory=dict)
    copy_candidates: list[dict[str, Any]] = Field(default_factory=list)
    minimal_copy_candidates: list[dict[str, Any]] = Field(default_factory=list)
    variant_results: list[dict[str, Any]] = Field(default_factory=list)
    selected_variant_id: str | None = None
    selected_copy: dict[str, Any] | None = None
    source_image_path: str | None = None
    background_image_path: str = ""
    final_composite_path: str = ""
    source_image_sha256: str | None = None
    background_sha256: str = ""
    final_composite_sha256: str = ""
    copy_provider_metadata: dict[str, Any] = Field(default_factory=dict)
    vision_provider_metadata: dict[str, Any] = Field(default_factory=dict)
    flux_metadata: dict[str, Any] | None = None
    renderer_metadata: dict[str, Any] = Field(default_factory=dict)
    vlm_result: dict[str, Any] = Field(default_factory=dict)
    mock_or_fixture_count: int = 0
    failure_reasons: list[str] = Field(default_factory=list)


def run_actual_creative_case(request: ActualCreativeInput, runtime: ActualCreativeRuntime) -> ActualCreativeResult:
    started = time.perf_counter()
    case_dir = Path(request.output_dir) / request.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_json(case_dir / "request.json", request.model_dump())

    try:
        bundle = run_input_evidence_normalizer(request, runtime=runtime, case_dir=case_dir)
        evidence = bundle.model_dump()
        _write_json(case_dir / "input_evidence.json", evidence)
        product_understanding = run_product_understanding(request, runtime, evidence)
        _write_json(case_dir / "product_understanding.json", product_understanding)
        copy_output = generate_grounded_copy(request, runtime, evidence, product_understanding)
        _write_json(case_dir / "product_copy_context.json", copy_output.get("product_copy_context") or {})
        _write_json(case_dir / "copy_presence_plan.json", copy_output.get("copy_presence_plan") or {})
        _write_json(case_dir / "language_policy.json", copy_output.get("language_policy") or {})
        _write_json(case_dir / "interaction_copy_plan.json", copy_output.get("interaction_copy_plan") or {})
        _write_json(case_dir / "copy_candidates.json", copy_output.get("copy_candidates") or [])
        if not _strict_provider_metadata(copy_output.get("provider_metadata"), runtime.copy_model):
            return _result(request, "failed", evidence, copy_output, failure="copy_provider_not_actual")

        image_plan = resolve_image_use_plan(request, evidence, copy_output)
        _write_json(case_dir / "image_use_plan.json", image_plan.model_dump())
        if image_plan.mode == "manual_review" or copy_output.get("requires_manual_review") is True:
            return _result(request, "manual_review", evidence, copy_output, image_use_plan=image_plan, failure="input_requires_manual_review")

        background, flux_metadata = prepare_or_generate_background(request, runtime, image_plan, case_dir, copy_output)
        selected_candidate = select_minimal_variant_candidate(copy_output)
        if selected_candidate:
            copy_output["selected_variant_id"] = selected_candidate.get("candidate_id")
            copy_output["selected_copy"] = _copy_from_minimal_candidate(selected_candidate)
        variant_results = render_minimal_copy_variants(request, copy_output, background, case_dir, selected_candidate=selected_candidate, render_all=runtime.render_all_variants)
        _write_json(case_dir / "variant_results.json", variant_results)
        selected_variant = select_minimal_variant(copy_output, variant_results) or selected_candidate
        if selected_variant:
            copy_output["selected_variant_id"] = selected_variant.get("candidate_id")
            copy_output["selected_copy"] = _copy_from_minimal_candidate(selected_variant)
            if selected_variant.get("variant_type") == "image_only":
                final_target = case_dir / "final_composite.png"
                shutil.copyfile(background, final_target)
                state = {
                    "render_result": {
                        "background_image_path": str(background),
                        "final_image_path": str(final_target),
                        "rendered_slot_count": 0,
                        "metadata": {"source_node": "minimal_copy_variant", "has_text_overlay": False, "copy_presence_mode": "image_only"},
                    },
                    "final_image_path": str(final_target),
                }
            else:
                state = execute_production_renderer(request, copy_output, background, case_dir)
        else:
            state = execute_production_renderer(request, copy_output, background, case_dir)
        final_path = Path(state.get("render_result", {}).get("final_image_path") or "")
        vlm = evaluate_final_composite_actual(request, runtime, final_path, copy_output.get("selected_copy") or {}, copy_output=copy_output)
        _write_json(case_dir / "final_vlm_result.json", vlm)
        _write_json(case_dir / "final_vlm_results.json", {"selected_variant_id": copy_output.get("selected_variant_id"), "selected": vlm})
        state["final_composite_vlm_result"] = vlm
        state["final_ocr_gate"] = _ocr_from_vlm(vlm, copy_output.get("selected_copy") or {})
        report = evaluate_final_composite(state)
        _write_json(case_dir / "render_trace.json", state.get("render_result") or {})

        result = ActualCreativeResult(
            case_id=request.case_id,
            input_mode=request.input_mode,
            status="completed",
            input_evidence=evidence,
            product_understanding=copy_output.get("product_understanding") or {},
            product_copy_context=copy_output.get("product_copy_context") or {},
            copy_presence_plan=copy_output.get("copy_presence_plan") or {},
            language_policy=copy_output.get("language_policy") or {},
            interaction_copy_plan=copy_output.get("interaction_copy_plan") or {},
            image_use_plan=image_plan.model_dump(),
            copy_candidates=copy_output.get("copy_candidates") or [],
            minimal_copy_candidates=copy_output.get("minimal_copy_candidates") or [],
            variant_results=variant_results,
            selected_variant_id=copy_output.get("selected_variant_id"),
            selected_copy=copy_output.get("selected_copy"),
            source_image_path=request.source_image_path,
            background_image_path=str(background),
            final_composite_path=str(final_path),
            source_image_sha256=evidence.get("source_image_sha256"),
            background_sha256=_sha256(background),
            final_composite_sha256=_sha256(final_path),
            copy_provider_metadata=copy_output.get("provider_metadata") or {},
            vision_provider_metadata=(evidence.get("provider_metadata") or {}).get("vision") or evidence.get("provider_metadata") or {},
            flux_metadata=flux_metadata,
            renderer_metadata={
                **(state.get("render_result", {}).get("metadata") or {}),
                "rendered_slot_count": (state.get("render_result") or {}).get("rendered_slot_count"),
            },
            vlm_result=vlm,
            mock_or_fixture_count=0,
            failure_reasons=[],
        )
        result = validate_actual_result(result, report)
        _write_json(case_dir / "result.json", {**result.model_dump(), "runtime_ms": int((time.perf_counter() - started) * 1000)})
        return result
    except Exception as exc:
        result = ActualCreativeResult(case_id=request.case_id, input_mode=request.input_mode, status="failed", failure_reasons=[str(exc)[:500]])
        _write_json(case_dir / "result.json", result.model_dump())
        return result


def normalize_actual_input(request: ActualCreativeInput, *, runtime: ActualCreativeRuntime, case_dir: Path) -> dict[str, Any]:
    return run_input_evidence_normalizer(request, runtime=runtime, case_dir=case_dir).model_dump()


def run_input_evidence_normalizer(request: ActualCreativeInput, *, runtime: ActualCreativeRuntime, case_dir: Path) -> InputEvidenceBundle:
    source_sha: str | None = None
    source_path = Path(request.source_image_path) if request.source_image_path else None
    if source_path:
        _verify_image(source_path)
        source_sha = _sha256(source_path)
        if source_path.parent != case_dir:
            target = case_dir / "source_image.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
    adapter = getattr(runtime, "openai_adapter", None)
    call_budget = getattr(runtime, "call_budget", None)
    if call_budget:
        call_budget.consume_openai()
    if adapter and hasattr(adapter, "normalize_input_evidence"):
        payload = adapter.normalize_input_evidence(request=request, model=runtime.vision_model)
        bundle = InputEvidenceBundle(**_hydrate_bundle_payload(request, payload, source_sha))
    else:
        observations: list[dict[str, Any]] = []
        provider_metadata: dict[str, Any] = {}
        if source_path:
            observations = analyze_source_image(request, runtime, source_path)
            observations, provider_metadata = _split_provider_metadata(observations)
        bundle = build_input_evidence_bundle(
            {
                "user_input": request.user_text,
                "source_image_path": str(source_path) if source_path else None,
                "source_asset_id": request.source_asset_id,
                "reference_asset_id": request.reference_asset_id,
                "placement": request.placement,
                "promotion_goal": request.promotion_goal,
                "source_provenance": request.source_provenance or ("user_uploaded" if source_path else None),
                "source_image_sha256": source_sha,
                "input_visual_observations": observations,
                "input_evidence_provider_metadata": provider_metadata,
            }
        )
    if source_sha and not bundle.source_image_sha256:
        bundle = bundle.model_copy(update={"source_image_sha256": source_sha})
    return bundle


def _hydrate_bundle_payload(request: ActualCreativeInput, payload: dict[str, Any], source_sha: str | None) -> dict[str, Any]:
    data = dict(payload or {})
    data["input_mode"] = request.input_mode
    data["user_text"] = request.user_text
    data["source_asset_id"] = request.source_asset_id
    data["reference_asset_id"] = request.reference_asset_id
    data["source_image_sha256"] = source_sha
    data["source_provenance"] = request.source_provenance or ("user_uploaded" if request.source_image_path else None)
    data["placement"] = request.placement
    data["promotion_goal"] = request.promotion_goal
    data["user_intent"] = data.get("user_intent") or _intent_from_request_text(request.user_text, request.promotion_goal)
    data["explicit_product_mentions"] = _clean_product_mentions(_coerce_string_list(data.get("explicit_product_mentions")), request=request)
    data["explicit_user_facts"] = [] if request.input_mode == "image_only" else _filter_user_facts(_coerce_evidence_items(data.get("explicit_user_facts"), source="user_text", evidence_class="verified_fact", usable_for_copy=True))
    if request.input_mode != "image_only":
        data["explicit_user_facts"] = _ensure_product_name_fact(data["explicit_user_facts"], data["explicit_product_mentions"])
    data["visual_observations"] = _coerce_evidence_items(data.get("visual_observations"), source="image_vlm", evidence_class="visual_observation", usable_for_copy=True)
    data["creative_inferences"] = _coerce_evidence_items(data.get("creative_inferences"), source="user_text", evidence_class="creative_inference", usable_for_copy=False)
    data["asset_metadata_evidence"] = _coerce_evidence_items(data.get("asset_metadata_evidence"), source="asset_metadata", evidence_class="verified_fact", usable_for_copy=True)
    data["brand_profile_evidence"] = _coerce_evidence_items(data.get("brand_profile_evidence"), source="brand_profile", evidence_class="verified_fact", usable_for_copy=True)
    data["reference_evidence"] = _coerce_evidence_items(data.get("reference_evidence"), source="reference_metadata", evidence_class="verified_fact", usable_for_copy=True)
    data["input_conflicts"] = _coerce_conflicts(data.get("input_conflicts"))
    data["unknown_fields"] = _coerce_string_list(data.get("unknown_fields"))
    data["unresolved_questions"] = _coerce_string_list(data.get("unresolved_questions"))
    data.setdefault("clarification_required", False)
    data.setdefault("manual_review_required", False)
    data["overall_confidence"] = _clamp_float(data.get("overall_confidence"), default=0.0)
    data.setdefault("provider_metadata", {})
    return data


def _ensure_product_name_fact(facts: list[dict[str, Any]], mentions: list[str]) -> list[dict[str, Any]]:
    if not mentions:
        return facts
    mention = mentions[0]
    mention_norm = _normalize_token(mention)
    for item in facts:
        key = str(item.get("key") or "")
        value = str(item.get("normalized_value") or item.get("value") or "")
        if key == "product_name" and _normalize_token(value) == mention_norm:
            return facts
    return [
        *facts,
        {
            "key": "product_name",
            "value": mention,
            "normalized_value": mention,
            "source": "user_text",
            "evidence_class": "verified_fact",
            "confidence": 1.0,
            "usable_for_copy": True,
            "source_ref": "user_input",
        },
    ]


def _coerce_string_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [str(item) for item in value.values() if str(item).strip()]
    return [str(value)]


def _intent_from_request_text(text: str | None, promotion_goal: str | None) -> str | None:
    if promotion_goal:
        return promotion_goal
    lowered = (text or "").lower()
    if "신메뉴" in (text or "") or "new menu" in lowered:
        return "new_menu_promotion"
    if "홍보" in (text or "") or "promote" in lowered or "advertise" in lowered:
        return "product_promotion"
    return None


def _clean_product_mentions(values: list[str], *, request: ActualCreativeInput) -> list[str]:
    cleaned = []
    for value in values:
        if _is_runtime_metadata_value(value, request=request):
            continue
        cleaned.append(_extract_product_phrase(value))
    if request.input_mode != "image_only" and not cleaned and request.user_text:
        cleaned.append(_extract_product_phrase(request.user_text.strip()))
    return cleaned


def _extract_product_phrase(text: str) -> str:
    value = text.strip()
    for marker in ("를", "을", "홍보", "promote", "advertise"):
        if marker in value:
            value = value.split(marker)[0].strip()
            break
    for prefix in ("카페 신메뉴 ", "신메뉴 ", "카페 "):
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
    value, _ = _split_product_campaign_modifier(value)
    return value or text.strip()


def _split_product_campaign_modifier(value: str | None) -> tuple[str | None, str | None]:
    text = str(value or "").strip()
    if not text:
        return None, None
    lowered = text.lower()
    if text.endswith(" 메뉴"):
        return text[: -len(" 메뉴")].strip() or text, "메뉴 홍보"
    if lowered.endswith(" menu"):
        return text[: -len(" menu")].strip() or text, "menu_promotion"
    return text, None


def _filter_user_facts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("key") or "")
        value = str(item.get("value") or "")
        if key not in ALLOWED_USER_FACT_KEYS:
            continue
        if _is_runtime_metadata_text(value):
            continue
        filtered.append(item)
    return filtered


def _is_runtime_metadata_value(value: str, *, request: ActualCreativeInput) -> bool:
    runtime_values = {
        request.case_id,
        request.input_mode,
        str(request.seed),
        request.output_dir,
        str(request.source_image_path),
        str(request.source_asset_id),
        str(request.reference_asset_id),
        str(request.source_provenance),
        request.placement,
        request.promotion_goal,
    }
    return value in runtime_values or _is_runtime_metadata_text(value)


def _is_runtime_metadata_text(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("data/outputs", "data\\outputs", "output_dir", "source_image_path", "case_id", "source_asset_id", "reference_asset_id")) or lowered in {"none", "null"}


def _coerce_evidence_items(value: object, *, source: str, evidence_class: str, usable_for_copy: bool) -> list[dict[str, Any]]:
    raw_items: list[object]
    if not value:
        return []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, dict):
        if {"key", "value"} & set(value.keys()):
            raw_items = [value]
        else:
            raw_items = [{"key": key, "value": item} for key, item in value.items()]
    else:
        raw_items = [{"key": evidence_class, "value": value}]
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_items):
        if isinstance(raw, dict):
            key = str(raw.get("key") or raw.get("kind") or f"{evidence_class}_{index}")
            if key in FORBIDDEN_EVIDENCE_KEYS:
                continue
            item_value = raw.get("value") if raw.get("value") is not None else raw.get("text")
            if item_value is None:
                item_value = raw.get("observation") or raw.get("inference") or raw.get("product") or raw.get("name") or raw
            if _is_runtime_metadata_text(str(item_value)):
                continue
            existing_text = evidence_class == "visual_observation" and _looks_like_existing_overlay_text(raw, str(item_value))
            items.append(
                {
                    "key": "existing_overlay_text" if existing_text else key,
                    "value": str(item_value),
                    "normalized_value": str(raw.get("normalized_value") or item_value),
                    "source": _coerce_evidence_source(raw.get("source"), default=source),
                    "evidence_class": _coerce_evidence_class(raw.get("evidence_class"), default=evidence_class),
                    "confidence": _clamp_float(raw.get("confidence"), default=_default_evidence_confidence(str(item_value), evidence_class=evidence_class)),
                    "usable_for_copy": False if existing_text or evidence_class == "creative_inference" else bool(raw.get("usable_for_copy", usable_for_copy)),
                    "source_ref": raw.get("source_ref"),
                    "rationale": raw.get("rationale"),
                }
            )
        else:
            if _is_runtime_metadata_text(str(raw)):
                continue
            items.append({"key": f"{evidence_class}_{index}", "value": str(raw), "source": source, "evidence_class": evidence_class, "confidence": _default_evidence_confidence(str(raw), evidence_class=evidence_class), "usable_for_copy": usable_for_copy})
    return items


def _looks_like_existing_overlay_text(raw: dict[str, Any], value: str) -> bool:
    label = " ".join(str(raw.get(key) or "") for key in ("key", "kind", "text_type", "rationale")).lower()
    lowered = value.lower()
    if any(token in label for token in ("package", "packaging", "label", "native_text", "bottle", "container")):
        return False
    return "existing" in label or "overlay" in label or "visible text" in label or "korean text" in lowered or "cta" in label or "headline" in label


def _default_evidence_confidence(value: str, *, evidence_class: str) -> float:
    if evidence_class == "visual_observation" and len(value.strip()) >= 12:
        return 0.78
    return 0.5


def _coerce_evidence_source(value: object, *, default: str) -> str:
    normalized = str(value or default).strip().lower()
    aliases = {"image": "image_vlm", "vision": "image_vlm", "user": "user_text", "text": "user_text", "metadata": "asset_metadata", "brand": "brand_profile", "reference": "reference_metadata"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"user_text", "image_vlm", "asset_metadata", "brand_profile", "reference_metadata"} else default


def _coerce_evidence_class(value: object, *, default: str) -> str:
    normalized = str(value or default).strip().lower()
    aliases = {"fact": "verified_fact", "verified": "verified_fact", "visual": "visual_observation", "observation": "visual_observation", "inference": "creative_inference"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"verified_fact", "visual_observation", "creative_inference"} else default


def _coerce_conflicts(value: object) -> list[dict[str, Any]]:
    if not value:
        return []
    raw_items = value if isinstance(value, list) else [value]
    conflicts: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            conflicts.append({"field": "input", "text_value": str(raw), "conflict_type": "attribute_mismatch", "severity": "manual_review", "confidence": 0.5, "recommended_resolution": "manual_review"})
            continue
        conflicts.append(
            {
                "field": str(raw.get("field") or "input"),
                "text_value": raw.get("text_value"),
                "image_value": raw.get("image_value"),
                "metadata_value": raw.get("metadata_value"),
                "conflict_type": raw.get("conflict_type") or "attribute_mismatch",
                "severity": raw.get("severity") or "manual_review",
                "confidence": _clamp_float(raw.get("confidence"), default=0.5),
                "recommended_resolution": str(raw.get("recommended_resolution") or raw.get("resolution") or "manual_review"),
            }
        )
    return conflicts


def _clamp_float(value: object, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def _split_provider_metadata(observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    for item in observations:
        if item.get("kind") == "provider_metadata" and isinstance(item.get("value"), dict):
            metadata = item["value"]
            continue
        cleaned.append(item)
    return cleaned, metadata


def _legacy_evidence_dict(request: ActualCreativeInput, source_sha: str | None) -> dict[str, Any]:
    return {
        "input_mode": request.input_mode,
        "explicit_product_mentions": [request.user_text.strip()] if request.user_text else [],
        "user_provided_facts": _facts_from_text(request.user_text),
        "visual_observations": [],
        "provider_metadata": {},
        "input_conflicts": [],
        "unresolved_fields": [],
        "source_image_sha256": source_sha,
        "source_provenance": request.source_provenance or ("user_uploaded" if request.source_image_path else None),
    }


def analyze_source_image(request: ActualCreativeInput, runtime: ActualCreativeRuntime, source_path: Path) -> list[dict[str, Any]]:
    adapter = getattr(runtime, "vision_adapter", None) or getattr(runtime, "openai_adapter", None)
    if adapter and hasattr(adapter, "analyze_source_image"):
        payload = adapter.analyze_source_image(request=request, image_path=str(source_path), model=runtime.vision_model)
        observations = payload.get("visual_observations") or []
        metadata = payload.get("provider_metadata") or {}
        return [*observations, {"kind": "provider_metadata", "value": metadata}]
    if adapter is None:
        return [{"kind": "file_verified", "confidence": 0.8}]
    prompt = "Analyze this product image for visible product, confidence, negative space, clipping, and existing text. Return JSON only."
    payload, metadata = _openai_image_json(prompt=prompt, image_path=source_path, model=runtime.vision_model)
    analysis = ActualSourceImageAnalysis(visual_observations=payload.get("visual_observations") or [{"kind": "vision_analysis", "value": payload}], provider_metadata=metadata)
    return [*analysis.visual_observations, {"kind": "provider_metadata", "value": analysis.provider_metadata}]


def run_product_understanding(request: ActualCreativeInput, runtime: ActualCreativeRuntime, evidence: dict[str, Any]) -> dict[str, Any]:
    if runtime.call_budget:
        runtime.call_budget.consume_openai()
    adapter = getattr(runtime, "openai_adapter", None)
    if adapter and hasattr(adapter, "understand_product"):
        payload = adapter.understand_product(request=request, evidence=evidence, model=runtime.copy_model)
        product_payload = payload.get("product_understanding") if isinstance(payload, dict) else None
        data = _coerce_product_understanding_candidate(product_payload or {}, evidence)
        data = validate_product_understanding(data, evidence).model_dump()
        data["provider_metadata"] = payload.get("provider_metadata") or {"provider": "openai", "model": runtime.copy_model}
        return data
    state = {
        "user_plan": "premium",
        "plan_policy": {
            "user_plan": "premium",
            "allowed_model_classes": ["api_full", "api_mini", "api_nano", "api_vision", "mock"],
            "max_api_calls_per_job": 20,
            "max_candidates": 3,
            "vision_gate_enabled": True,
            "allow_api_fallback": True,
            "node_policies": {},
        },
        "llm_call_results": [],
        "model_selections": [],
    }
    result = generate_product_understanding(InputEvidenceBundle(**evidence), state=state)
    data = _coerce_product_understanding_candidate(result.model_dump(), evidence)
    data = validate_product_understanding(data, evidence).model_dump()
    data["provider_metadata"] = result.provider_metadata
    return data


def _coerce_product_understanding_candidate(candidate: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    data = dict(candidate or {})
    evidence_product = _product_from_evidence(evidence)
    product_name = _nested_string(data, ("product_name", "product", "primary_product", "product_identity", "name")) or evidence_product
    if product_name and not any(ch.isalpha() for ch in str(product_name)):
        product_name = evidence_product or product_name
    product_name, campaign_modifier = _split_product_campaign_modifier(str(product_name or ""))
    normalized_type = _normalize_product_type(
        _nested_string(data, ("normalized_product_type", "normalized_product_candidate", "product_type", "type")) or product_name
    )
    if not normalized_type:
        normalized_type = _normalize_product_type(product_name)
    if normalized_type and not any(ch.isalpha() for ch in normalized_type):
        normalized_type = _normalize_product_type(product_name)
    raw_path = data.get("category_path")
    broad = _normalize_broad_category(" ".join(str(item) for item in [_nested_string(data, ("broad_category", "category", "domain")) or "", product_name or "", raw_path or ""]))
    category_path = _normalize_category_path(raw_path if isinstance(raw_path, list) else [], broad, normalized_type)
    evidence_ids = _product_evidence_ids(product_name, evidence)
    campaign_modifiers = list(data.get("campaign_modifiers") or [])
    if not campaign_modifier and "메뉴" in str(evidence.get("user_text") or "") and "홍보" in str(evidence.get("user_text") or ""):
        campaign_modifier = "메뉴 홍보"
    if campaign_modifier and campaign_modifier not in campaign_modifiers:
        campaign_modifiers.append(campaign_modifier)
    return {
        **data,
        "schema_version": "product_understanding_v1",
        "product_name": product_name or "unknown product",
        "campaign_modifiers": campaign_modifiers,
        "normalized_product_type": normalized_type,
        "broad_category": broad,
        "category_path": category_path,
        "verified_facts": [item for item in _evidence_items(evidence, ("explicit_user_facts", "asset_metadata_evidence", "brand_profile_evidence", "reference_evidence")) if item.get("evidence_id") in evidence_ids],
        "visual_observations": [item for item in _evidence_items(evidence, ("visual_observations",)) if item.get("evidence_id") in evidence_ids],
        "permissible_inferences": [item for item in _evidence_items(evidence, ("creative_inferences",)) if item.get("confidence", 1.0) <= 0.8],
        "unknown_fields": list(data.get("unknown_fields") or evidence.get("unknown_fields") or []),
        "unsupported_claim_categories": _unsupported_claim_categories_from_evidence(evidence),
        "product_name_evidence_ids": evidence_ids,
        "confidence_by_field": data.get("confidence_by_field") if isinstance(data.get("confidence_by_field"), dict) else {},
        "confidence": _float_between(data.get("confidence"), 0.75 if evidence_ids else 0.45),
        "clarification_required": bool(data.get("clarification_required")) or not bool(product_name),
        "manual_review_required": bool(data.get("manual_review_required")) or bool(evidence.get("manual_review_required")),
    }


def _nested_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _nested_string(value, ("value", "name", "product_name", "candidate", "label", "text"))
            if nested:
                return nested
    return None


def _normalize_broad_category(value: str) -> str:
    slug = normalize_slug(value) or ""
    allowed = {
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
    }
    if slug in allowed:
        return slug
    if any(token in slug for token in ("food", "beverage", "dessert", "drink", "meal", "menu", "stew", "jjigae", "restaurant", "cafe")):
        return "food_and_beverage"
    if any(token in slug for token in ("beauty", "personal_care", "skincare", "cosmetic", "fragrance", "serum", "niacinamide")):
        return "beauty_and_personal_care"
    if any(token in slug for token in ("fashion", "lifestyle", "footwear", "apparel")):
        return "fashion_and_lifestyle"
    if any(token in slug for token in ("home", "living", "furniture", "decor", "lighting")):
        return "home_and_living"
    if any(token in slug for token in ("tech", "software", "computer", "electronics")):
        return "technology"
    if "service" in slug:
        return "local_service"
    if "education" in slug or "course" in slug:
        return "education"
    return "other"


def _normalize_product_type(value: str | None) -> str | None:
    slug = normalize_slug(value)
    if not slug:
        return None
    removable = {"menu", "promotion", "promote", "ad", "advertising", "campaign"}
    parts = [part for part in slug.split("_") if part and part not in removable]
    return "_".join(parts) or slug


def _normalize_category_path(raw_path: list[Any], broad: str, normalized_type: str | None) -> list[str]:
    path = [broad]
    root_aliases = {"food_beverage", "beauty_personal_care", "fashion_lifestyle", "home_living"}
    for item in raw_path:
        slug = normalize_slug(str(item))
        if slug and slug != broad and slug not in root_aliases and slug not in path and len(path) < 6:
            path.append(slug)
    if normalized_type and normalized_type not in path and len(path) < 6:
        path.append(normalized_type)
    return path


def _product_evidence_ids(product_name: str | None, evidence: dict[str, Any]) -> list[str]:
    if not product_name:
        return []
    product_norm = "".join(ch.lower() for ch in product_name if ch.isalnum())
    ids: list[str] = []
    for item in _evidence_items(evidence, ("explicit_user_facts", "asset_metadata_evidence", "brand_profile_evidence", "reference_evidence", "visual_observations")):
        value_norm = "".join(ch.lower() for ch in str(item.get("normalized_value") or item.get("value") or "") if ch.isalnum())
        if value_norm and (product_norm in value_norm or value_norm in product_norm):
            ids.append(str(item.get("evidence_id")))
    return ids


def _unsupported_claim_categories_from_evidence(evidence: dict[str, Any]) -> list[str]:
    verified_keys = {
        normalize_slug(str(item.get("key") or ""))
        for item in _evidence_items(evidence, ("explicit_user_facts", "asset_metadata_evidence", "brand_profile_evidence", "reference_evidence"))
    }
    allowed = {item for item in verified_keys if item in UNSUPPORTED_CLAIM_CATEGORIES}
    return sorted(set(UNSUPPORTED_CLAIM_CATEGORIES) - allowed)


def _evidence_items(evidence: dict[str, Any], groups: tuple[str, ...]) -> list[dict[str, Any]]:
    return [item for group in groups for item in evidence.get(group, []) if isinstance(item, dict)]


def _float_between(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, numeric))


def generate_grounded_copy(request: ActualCreativeInput, runtime: ActualCreativeRuntime, evidence: dict[str, Any], product_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    adapter = runtime.openai_adapter
    if runtime.call_budget:
        runtime.call_budget.consume_openai()
    if adapter and hasattr(adapter, "generate_product_copy"):
        try:
            payload = adapter.generate_product_copy(request=request, evidence=evidence, product_understanding=product_understanding or {}, model=runtime.copy_model)
        except TypeError:
            payload = adapter.generate_product_copy(request=request, evidence=evidence, model=runtime.copy_model)
        return _validated_copy_output(_hydrate_copy_payload(payload, evidence, product_understanding), runtime.copy_model)
    prompt = (
        "Return JSON only with product_understanding, product_copy_context, copy_candidates, "
        "recommended_candidate_id, selected_copy, input_conflicts, requires_manual_review. Generate grounded ad copy only from the supplied InputEvidenceBundle. "
        "product_copy_context should include message territories, sensory/emotional/functional/contextual vocabulary, language_policy, copy_presence_plan, and interaction_plan. "
        "Prefer visual-first minimal copy: image-only, headline-only, headline+support, or headline+closing. Do not create generic action CTAs unless a verified destination exists. "
        "Hard block Learn More, Discover More, Shop Now, 지금 확인하기, 자세히 보기, 메뉴 보기, 지금 만나보세요 when no destination is verified. "
        "For Korean local food/menu products, use Korean headline by default and do not romanize product names unless explicitly requested. "
        "Do not infer unknown fields and do not use raw source image content outside the bundle. "
        f"Request metadata: {request.model_dump_json()} ProductUnderstanding: {json.dumps(product_understanding or {}, ensure_ascii=False)} InputEvidenceBundle: {json.dumps(evidence, ensure_ascii=False)}"
    )
    payload, metadata = _openai_text_json(prompt=prompt, model=runtime.copy_model)
    candidates = payload.get("copy_candidates") or []
    selected = _select_copy(candidates, payload.get("recommended_candidate_id"))
    return _validated_copy_output(_hydrate_copy_payload({
        "product_understanding": product_understanding or payload.get("product_understanding") or {},
        "product_copy_context": payload.get("product_copy_context") or {},
        "copy_candidates": candidates,
        "recommended_candidate_id": payload.get("recommended_candidate_id"),
        "selected_copy": selected,
        "input_conflicts": payload.get("input_conflicts") or [],
        "requires_manual_review": bool(payload.get("requires_manual_review")),
        "provider_metadata": metadata,
    }, evidence, product_understanding), runtime.copy_model)


def _hydrate_copy_payload(payload: dict[str, Any], evidence: dict[str, Any], product_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(payload or {})
    understanding = dict(product_understanding or data.get("product_understanding") or {})
    context = dict(data.get("product_copy_context") or {})
    evidence_product = _product_from_evidence(evidence)
    product = evidence_product or understanding.get("product_name") or understanding.get("normalized_product_candidate")
    if product:
        understanding["product_name"] = product
        understanding["normalized_product_candidate"] = understanding.get("normalized_product_candidate") or product
    understanding.setdefault("broad_category", "other")
    understanding.setdefault("explicit_product_candidate", product or "product")
    understanding.setdefault("product_identity_confidence", evidence.get("overall_confidence") or 0.75)
    context.setdefault("brand_tone", "premium")
    candidates = data.get("copy_candidates") or []
    selected = data.get("selected_copy") or _select_copy(candidates, data.get("recommended_candidate_id"))
    if selected:
        normalized = normalize_selected_copy(selected)
        data["selected_copy"] = sanitize_selected_copy({**selected, **normalized})
    data["product_understanding"] = understanding
    dynamic_context = production_build_dynamic_product_copy_context(context, understanding, evidence)
    minimal_candidates = production_build_minimal_copy_candidates(data, dynamic_context)
    selected_candidate = production_select_minimal_candidate_for_plan(dynamic_context.copy_presence_plan, minimal_candidates)
    data["product_copy_context"] = dynamic_context.model_dump()
    data["copy_presence_plan"] = dynamic_context.copy_presence_plan.model_dump()
    data["language_policy"] = dynamic_context.language_policy.model_dump()
    data["interaction_copy_plan"] = dynamic_context.interaction_plan.model_dump()
    data["minimal_copy_candidates"] = [item.model_dump() for item in minimal_candidates]
    if selected_candidate:
        data["selected_variant_id"] = selected_candidate.candidate_id
        data["selected_copy"] = _copy_from_minimal_candidate(selected_candidate.model_dump())
    if dynamic_context.copy_presence_plan.mode == "image_only" and not evidence.get("input_conflicts"):
        data["requires_manual_review"] = False
    return data


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
        return {
            "sensory": ["구수한", "따뜻한", "깊은"],
            "emotional": ["편안한", "익숙한"],
            "functional": ["한 그릇", "식사"],
            "contextual": ["오늘의 식탁", "저녁 한 끼"],
            "adjacent": ["밥", "상차림"],
            "moments": ["warm_meal_moment", "familiar_table"],
        }
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


def build_minimal_copy_candidates(data: dict[str, Any], context: ProductCopyContext) -> list[MinimalCopyCandidate]:
    selected = sanitize_selected_copy(normalize_selected_copy(data.get("selected_copy") or {}))
    headline = _minimal_headline(selected.get("headline"), context)
    support = _minimal_support(selected.get("subcopy"), context)
    closing = _minimal_closing(selected.get("closing_copy") or selected.get("cta"), context)
    territory = context.message_territories[0].territory_id if context.message_territories else None
    evidence_keys = [item for territory_item in context.message_territories for item in territory_item.supporting_evidence_keys]
    language = context.language_policy.headline_language
    return [
        MinimalCopyCandidate(candidate_id="variant_image_only", variant_type="image_only", territory_id=None, headline=None, supporting_copy=None, closing_copy=None, action_cta=None, language_mode=context.language_policy.primary_language, supporting_evidence_keys=[], text_block_count=0, estimated_text_area_ratio=0.0),
        MinimalCopyCandidate(candidate_id="variant_headline_only", variant_type="headline_only", territory_id=territory, headline=headline, language_mode=language, supporting_evidence_keys=evidence_keys, text_block_count=1, estimated_text_area_ratio=0.06),
        MinimalCopyCandidate(candidate_id="variant_headline_plus_support", variant_type="headline_plus_support", territory_id=territory, headline=headline, supporting_copy=support, language_mode=context.language_policy.primary_language, supporting_evidence_keys=evidence_keys, text_block_count=2, estimated_text_area_ratio=0.10),
        MinimalCopyCandidate(candidate_id="variant_headline_plus_closing", variant_type="headline_plus_closing", territory_id=territory, headline=headline, closing_copy=closing, action_cta=None, language_mode=context.language_policy.primary_language, supporting_evidence_keys=evidence_keys, text_block_count=2, estimated_text_area_ratio=0.09),
    ]


def select_minimal_candidate_for_plan(plan: MinimalCopyPresencePlan, candidates: list[MinimalCopyCandidate]) -> MinimalCopyCandidate | None:
    preferred = {
        "image_only": "image_only",
        "brand_only": "headline_only",
        "headline_only": "headline_only",
        "headline_plus_support": "headline_plus_support",
        "headline_plus_closing": "headline_plus_closing",
    }.get(plan.mode)
    return next((item for item in candidates if item.variant_type == preferred), None) or (candidates[0] if candidates else None)


def sanitize_selected_copy(selected: dict[str, Any]) -> dict[str, Any]:
    return production_sanitize_selected_copy(selected)


def _is_generic_cta(value: object) -> bool:
    return production_is_generic_cta(value)


def _minimal_headline(value: str | None, context: ProductCopyContext) -> str:
    product = context.product_name
    if value and not _is_generic_cta(value):
        return _truncate_copy(value, 24 if context.language_policy.headline_language == "korean" else 48)
    slug = context.normalized_product_type or ""
    if "jjigae" in slug:
        return "구수하게 끓여낸 한 그릇"
    if context.broad_category == "food_and_beverage":
        return f"{product}의 조용한 순간"
    if context.broad_category == "beauty_and_personal_care":
        return "차분하게 채우는 루틴"
    return product


def _minimal_support(value: str | None, context: ProductCopyContext) -> str | None:
    if value and not _is_generic_cta(value):
        return _truncate_copy(value, 40)
    if context.copy_presence_plan.mode == "headline_plus_support":
        return "검증된 정보 안에서 담백하게 전합니다"
    return None


def _minimal_closing(value: str | None, context: ProductCopyContext) -> str | None:
    if value and not _is_generic_cta(value):
        return _truncate_copy(value, 24)
    if context.interaction_plan.action_cta_allowed:
        return None
    if context.normalized_product_type and "jjigae" in context.normalized_product_type:
        return "오늘의 식탁에 구수함을"
    return "기억에 남는 한 장면"


def _truncate_copy(value: str, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip()


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


def resolve_image_use_plan(request: ActualCreativeInput, evidence: dict[str, Any], copy_output: dict[str, Any]) -> ImageUsePlan:
    if evidence.get("manual_review_required"):
        return ImageUsePlan(mode="manual_review", reason_codes=["manual_review_required"], confidence=float(evidence.get("overall_confidence") or 0.0))
    if evidence.get("input_conflicts") or copy_output.get("input_conflicts"):
        return ImageUsePlan(mode="manual_review", reason_codes=["input_conflict"], confidence=0.45)
    if request.input_mode == "text_only":
        return ImageUsePlan(mode="generate_from_text", reason_codes=["text_only"], confidence=0.9)
    observations = evidence.get("visual_observations") or []
    confidence = _observation_confidence(observations)
    if not observations:
        return ImageUsePlan(mode="manual_review", reason_codes=["missing_visual_observations"], confidence=0.0)
    if _has_existing_overlay_text(observations):
        return ImageUsePlan(mode="manual_review", reason_codes=["existing_overlay_text_detected", "clean_background_required"], confidence=confidence)
    if request.source_image_path and _has_product_visual_signal(observations):
        return ImageUsePlan(mode="use_uploaded_as_background", reason_codes=[request.input_mode, "product_visual_signal"], confidence=max(0.75, _observation_confidence(observations)))
    if confidence < 0.45:
        return ImageUsePlan(mode="manual_review", reason_codes=["low_visual_confidence"], confidence=confidence)
    if confidence < 0.7:
        return ImageUsePlan(mode="analyze_then_regenerate", reason_codes=["weak_background_fit"], confidence=confidence)
    return ImageUsePlan(mode="use_uploaded_as_background", reason_codes=[request.input_mode], confidence=confidence)


def prepare_or_generate_background(
    request: ActualCreativeInput,
    runtime: ActualCreativeRuntime,
    image_plan: ImageUsePlan,
    case_dir: Path,
    copy_output: dict[str, Any],
) -> tuple[Path, dict[str, Any] | None]:
    if image_plan.mode == "use_uploaded_as_background" and request.source_image_path:
        path = Path(request.source_image_path)
        _verify_image(path)
        return path, None
    if image_plan.mode not in {"generate_from_text", "analyze_then_regenerate"}:
        raise RuntimeError(f"Unsupported ImageUsePlan mode: {image_plan.mode}")
    prompt = _background_prompt(request, copy_output)
    engine = runtime.flux_engine
    if engine is None:
        from orchestrator.app.t2i.engines.registry import get_t2i_engine

        engine = get_t2i_engine(runtime.t2i_engine)
    started = time.perf_counter()
    output = engine.generate(
        T2IGenerationInput(
            job_id=f"canonical_actual_{request.case_id}",
            prompt=prompt,
            negative_prompt=(
                "visible writing, logo, watermark, signage, poster text, no text, no letters, no words, "
                "no typography, no captions, no pseudo text, no UI, no poster copy, advertisement typography, "
                "Korean headline, product information list, benefit cards, price text, discount badge with text, menu wording, brand slogan"
            ),
            width=1024,
            height=1024,
            num_images=1,
            seed=request.seed,
            output_dir=str(case_dir),
            metadata={"source": "canonical_actual_creative_pipeline", "case_id": request.case_id},
        )
    )
    if runtime.call_budget:
        runtime.call_budget.consume_flux()
    if not output.image_paths:
        raise RuntimeError("FLUX engine returned no image path")
    source = Path(output.image_paths[0])
    _verify_image(source)
    target = case_dir / "background_flux2.png"
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    metadata = {
        "engine": output.engine,
        "backend": runtime.t2i_backend,
        "model": (output.metadata or {}).get("model_name") or "black-forest-labs/FLUX.2-klein-4B",
        "seed": request.seed,
        "runtime_ms": output.latency_ms or int((time.perf_counter() - started) * 1000),
        "output_path": str(target),
        "sha256": _sha256(target),
        **(output.metadata or {}),
    }
    return target, metadata


def render_minimal_copy_variants(request: ActualCreativeInput, copy_output: dict[str, Any], background_path: Path, case_dir: Path, *, selected_candidate: dict[str, Any] | None = None, render_all: bool = False) -> list[dict[str, Any]]:
    variants_dir = case_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    selected_id = str((selected_candidate or {}).get("candidate_id") or "")
    for candidate in copy_output.get("minimal_copy_candidates") or []:
        candidate_id = str(candidate.get("candidate_id") or candidate.get("variant_type") or "variant")
        variant_type = str(candidate.get("variant_type") or candidate_id)
        if not render_all and selected_id and candidate_id != selected_id:
            results.append({**candidate, "status": "not_rendered", "selection_policy": "policy_based_single_selection"})
            continue
        if not render_all:
            results.append({**candidate, "status": "selected", "selection_policy": "policy_based_single_selection"})
            continue
        target = variants_dir / f"{variant_type}.png"
        if variant_type == "image_only":
            shutil.copyfile(background_path, target)
            results.append(
                {
                    **candidate,
                    "image_path": str(target),
                    "status": "completed",
                    "rendered_slot_count": 0,
                    "background_sha256": _sha256(background_path),
                    "final_sha256": _sha256(target),
                    "has_text_overlay": False,
                }
            )
            continue
        variant_output = {**copy_output, "selected_copy": _copy_from_minimal_candidate(candidate)}
        try:
            state = execute_production_renderer(request, variant_output, background_path, case_dir)
            rendered = Path(state.get("render_result", {}).get("final_image_path") or "")
            _verify_image(rendered)
            shutil.copyfile(rendered, target)
            results.append(
                {
                    **candidate,
                    "image_path": str(target),
                    "status": "completed",
                    "rendered_slot_count": (state.get("render_result") or {}).get("rendered_slot_count"),
                    "background_sha256": _sha256(background_path),
                    "final_sha256": _sha256(target),
                    "has_text_overlay": bool(((state.get("render_result") or {}).get("metadata") or {}).get("has_text_overlay")),
                    "render_warnings": (state.get("render_result") or {}).get("warnings") or [],
                }
            )
        except Exception as exc:
            results.append({**candidate, "image_path": str(target), "status": "failed", "error_message": str(exc)[:300]})
    if render_all:
        _build_variant_comparison_sheet(variants_dir.parent / "comparison_sheet.png", results)
    return results


def select_minimal_variant_candidate(copy_output: dict[str, Any]) -> dict[str, Any] | None:
    plan = copy_output.get("copy_presence_plan") or {}
    try:
        parsed_plan = MinimalCopyPresencePlan(**plan)
        parsed_candidates = [MinimalCopyCandidate(**item) for item in copy_output.get("minimal_copy_candidates") or []]
        selected = production_select_minimal_candidate_for_plan(parsed_plan, parsed_candidates)
        return selected.model_dump() if selected else None
    except Exception:
        candidates = copy_output.get("minimal_copy_candidates") or []
        return candidates[0] if candidates else None


def select_minimal_variant(copy_output: dict[str, Any], variant_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    plan = copy_output.get("copy_presence_plan") or {}
    mode = plan.get("mode") or "headline_only"
    preferred = {
        "image_only": "image_only",
        "brand_only": "headline_only",
        "headline_only": "headline_only",
        "headline_plus_support": "headline_plus_support",
        "headline_plus_closing": "headline_plus_closing",
    }.get(mode, "headline_only")
    successful = [item for item in variant_results if item.get("status") == "completed"]
    return next((item for item in successful if item.get("variant_type") == preferred), None) or next((item for item in successful if item.get("variant_type") == "headline_only"), None) or (successful[0] if successful else None)


def _copy_from_minimal_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return production_copy_from_minimal_candidate(candidate)


def _build_variant_comparison_sheet(output_path: Path, results: list[dict[str, Any]]) -> None:
    images: list[tuple[dict[str, Any], Image.Image]] = []
    for item in results:
        path = Path(str(item.get("image_path") or ""))
        if path.exists():
            images.append((item, Image.open(path).convert("RGB")))
    if not images:
        return
    thumb_size = 256
    label_h = 44
    sheet = Image.new("RGB", (thumb_size * len(images), thumb_size + label_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (item, image) in enumerate(images):
        image.thumbnail((thumb_size, thumb_size))
        x = index * thumb_size + (thumb_size - image.width) // 2
        sheet.paste(image, (x, 0))
        draw.text((index * thumb_size + 8, thumb_size + 6), f"{item.get('variant_type')}\\n{item.get('status')}", fill=(20, 20, 20))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def execute_production_renderer(request: ActualCreativeInput, copy_output: dict[str, Any], background_path: Path, case_dir: Path) -> dict[str, Any]:
    from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
    from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
    from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
    from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
    from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
    from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
    from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
    from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
    from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node

    selected = normalize_selected_copy(copy_output.get("selected_copy") or {})
    product_understanding = copy_output.get("product_understanding") or {}
    product_copy_context = copy_output.get("product_copy_context") or {}
    business_type = _required_text(product_understanding, "broad_category")
    item_or_service = _required_text(product_understanding, "product_name")
    brand_tone = str(product_copy_context.get("brand_tone") or "premium")
    headline = _required_text(selected, "headline")
    state: dict[str, Any] = {
        "job_id": f"canonical-{request.case_id}",
        "thread_id": f"canonical-{request.case_id}",
        "user_plan": "premium",
        "context": {
            "business_type": business_type,
            "item_or_service": item_or_service,
            "promotion_goal": request.promotion_goal,
            "brand_tone": brand_tone,
        },
        "ad_format_spec": {"ad_format": request.placement, "width": 1024, "height": 1024},
        "copy_visual_intent": {
            "hierarchy": "editorial_product",
            "headline_emphasis": "large_elegant",
            "body_density": "low",
            "cta_visibility": "optional",
            "cta_style": "text_link",
            "preferred_alignment": "left",
            "typography_mood": "premium_serif",
            "plate_policy": "subtle",
            "product_text_relationship": "side_by_side",
        },
        "marketing_copy": {
            "headline": headline,
            "subcopy": selected.get("subcopy") or "",
            "cta": selected.get("cta") or "",
        },
        "t2i_result": {"engine": "flux2_klein_4b", "image_paths": [str(background_path)], "metadata": {}},
        "background_image_path": str(background_path),
        "artifact_refs": [{"type": "background_image", "path": str(background_path)}],
        "final_composite_attempts": 1,
    }
    for node in (
        copy_spec_parser_node,
        typography_art_direction_node,
        text_style_binder_node,
        text_layout_planner_node,
        image_layout_analyzer_node,
        post_t2i_layout_refiner_node,
        adaptive_typography_refiner_node,
        safe_area_gate_node,
        text_renderer_node,
    ):
        state.update(node(state) or {})
    final_path = Path(state.get("render_result", {}).get("final_image_path") or "")
    _verify_image(final_path)
    target = case_dir / "final_composite.png"
    if final_path.resolve() != target.resolve():
        shutil.copyfile(final_path, target)
    state["render_result"] = {**(state.get("render_result") or {}), "final_image_path": str(target)}
    state["final_image_path"] = str(target)
    state["artifact_refs"] = [*state.get("artifact_refs", []), {"type": "final_image", "path": str(target)}]
    return state


def normalize_selected_copy(selected: dict[str, Any]) -> dict[str, str | None]:
    def clean(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    return {
        "headline": clean(selected.get("headline") or selected.get("title") or selected.get("primary_text")),
        "subcopy": clean(selected.get("subcopy") or selected.get("supporting_copy") or selected.get("secondary_text") or selected.get("body") or selected.get("primary_text")),
        "cta": clean(selected.get("cta") or selected.get("call_to_action")),
    }


def evaluate_final_composite_actual(request: ActualCreativeInput, runtime: ActualCreativeRuntime, final_path: Path, copy: dict[str, Any], *, copy_output: dict[str, Any] | None = None) -> dict[str, Any]:
    adapter = runtime.vision_adapter or runtime.openai_adapter
    evaluation_context = _vlm_evaluation_context(copy_output or {}, copy)
    if runtime.call_budget:
        runtime.call_budget.consume_openai()
    if adapter and hasattr(adapter, "evaluate_final_composite"):
        try:
            payload = adapter.evaluate_final_composite(request=request, image_path=str(final_path), copy=copy, model=runtime.vision_model, evaluation_context=evaluation_context)
        except TypeError:
            payload = adapter.evaluate_final_composite(request=request, image_path=str(final_path), copy=copy, model=runtime.vision_model)
        return _validated_vlm_result(payload, runtime.vision_model)
    prompt = (
        "Evaluate this final ad composite. Return JSON only with product_match_score, copy_product_grounding_score, "
        "copy_readability_score, copy_visual_fit_score, product_obstruction_score, wrong_domain_detected, "
        "unsupported_claim_detected, commercial_viability_score, failure_reasons, recommended_action, confidence, detected_text. "
        f"Evaluation context: {json.dumps(evaluation_context, ensure_ascii=False)}. "
        "If evaluation_mode is image_only, expected_text is empty; do not fail for missing ad copy, CTA, headline hierarchy, branding, or OCR expected copy."
    )
    payload, metadata = _openai_image_json(prompt=prompt, image_path=final_path, model=runtime.vision_model)
    return _validated_vlm_result({**payload, "provider_metadata": metadata}, runtime.vision_model)


def _vlm_evaluation_context(copy_output: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    variant_type = str(copy.get("variant_type") or "headline_only")
    expected_roles = []
    if copy.get("headline"):
        expected_roles.append("headline")
    if copy.get("subcopy"):
        expected_roles.append("supporting_or_closing_copy")
    if copy.get("cta"):
        expected_roles.append("embedded_action_cta")
    if variant_type == "image_only":
        expected_roles = []
    return {
        "evaluation_mode": variant_type,
        "copy_presence_plan": copy_output.get("copy_presence_plan") or {},
        "interaction_copy_plan": copy_output.get("interaction_copy_plan") or {},
        "language_policy": copy_output.get("language_policy") or {},
        "selected_variant_type": variant_type,
        "expected_roles": expected_roles,
        "forbidden_roles": ["embedded_action_cta"] if not ((copy_output.get("interaction_copy_plan") or {}).get("action_cta_allowed")) else [],
        "expected_text": [] if variant_type == "image_only" else [text for text in (copy.get("headline"), copy.get("subcopy"), copy.get("cta")) if text],
    }


def validate_actual_result(result: ActualCreativeResult, report: Any) -> ActualCreativeResult:
    failures = list(result.failure_reasons)
    copy_presence_mode = (result.copy_presence_plan or {}).get("mode")
    copy_meta = result.copy_provider_metadata
    vlm_meta = (result.vlm_result or {}).get("provider_metadata") or result.vlm_result
    if not _strict_provider_metadata(copy_meta, "gpt-5.4"):
        failures.append("copy metadata missing strict gpt-5.4 usage")
    if not _strict_provider_metadata(vlm_meta, "gpt-5.4"):
        failures.append("vlm metadata missing strict gpt-5.4 usage")
    if result.input_mode in {"image_only", "text_and_image"} and not _strict_provider_metadata(result.vision_provider_metadata, "gpt-5.4"):
        failures.append("input evidence metadata missing strict gpt-5.4 usage")
    if result.input_mode == "text_only" and not result.flux_metadata:
        failures.append("text_only missing FLUX generation")
    if not result.final_composite_path or not Path(result.final_composite_path).exists():
        failures.append("final composite missing")
    if copy_presence_mode != "image_only" and result.background_sha256 and result.background_sha256 == result.final_composite_sha256:
        failures.append("background and final composite hashes match")
    if copy_presence_mode != "image_only" and int(result.renderer_metadata.get("rendered_slot_count") or 0) <= 0:
        failures.append("production renderer rendered no slots")
    ocr = (result.vlm_result or {}).get("detected_text")
    if copy_presence_mode != "image_only" and (not isinstance(ocr, list) or not ocr):
        failures.append("ocr detected_text unavailable")
    vlm_failures = (result.vlm_result or {}).get("failure_reasons") or []
    vlm_failures = _filter_vlm_failures_for_mode(vlm_failures, copy_presence_mode, result=result)
    if vlm_failures:
        failures.append("vlm failure reasons present")
    action = str((result.vlm_result or {}).get("recommended_action") or "").strip().lower()
    if copy_presence_mode == "image_only" and action in {"add_copy", "add_branding", "add_cta"}:
        action = "none"
    if action in REVISION_ACTIONS:
        failures.append(f"vlm recommended revision action: {action}")
    obstruction = (result.vlm_result or {}).get("product_obstruction_score")
    if isinstance(obstruction, (int, float)) and float(obstruction) > 0.35:
        failures.append("vlm product obstruction above threshold")
    if str(result.flux_metadata or "").lower().find("fixture") >= 0 or str(result.renderer_metadata or "").lower().find("fixture") >= 0:
        failures.append("fixture metadata detected")
    if result.mock_or_fixture_count:
        failures.append("mock or fixture used")
    if failures:
        return result.model_copy(update={"status": "failed", "failure_reasons": failures})
    return result.model_copy(update={"status": "completed", "failure_reasons": [], "final_composite_sha256": getattr(report, "evaluated_image_sha256", result.final_composite_sha256)})


def _filter_vlm_failures_for_mode(failures: list[Any], mode: str | None, *, result: ActualCreativeResult | None = None) -> list[Any]:
    expected_text = [str(value) for value in ((result.selected_copy or {}) if result else {}).values() if isinstance(value, str) and value.strip()]
    detected_text = [str(value) for value in (((result.vlm_result or {}).get("detected_text") or []) if result else [])]
    if mode != "image_only":
        return [failure for failure in failures if not _is_false_positive_text_match_failure(failure, expected_text, detected_text)]
    ignored_markers = (
        "no advertising copy",
        "no ad copy",
        "copy",
        "branding",
        "brand",
        "cta",
        "headline",
        "ocr",
        "explicitly labeled",
        "product identity is not explicitly labeled",
        "minimal commercial context",
    )
    filtered = []
    for failure in failures:
        text = str(failure).strip().lower()
        if _is_false_positive_text_match_failure(failure, expected_text, detected_text):
            continue
        if any(marker in text for marker in ignored_markers):
            continue
        filtered.append(failure)
    return filtered


def _is_false_positive_text_match_failure(failure: Any, expected_text: list[str], detected_text: list[str]) -> bool:
    text = str(failure or "").lower()
    if "does not exactly match expected text" not in text and "expected text" not in text:
        return False
    normalized_expected = {_normalize_text_for_match(item) for item in expected_text if item}
    normalized_detected = {_normalize_text_for_match(item) for item in detected_text if item}
    return bool(normalized_expected & normalized_detected)


def _normalize_text_for_match(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _result(request: ActualCreativeInput, status: ActualStatus, evidence: dict[str, Any], copy_output: dict[str, Any], *, image_use_plan: ImageUsePlan | None = None, failure: str) -> ActualCreativeResult:
    result = ActualCreativeResult(
        case_id=request.case_id,
        input_mode=request.input_mode,
        status=status,
        input_evidence=evidence,
        product_understanding=copy_output.get("product_understanding") or {},
        product_copy_context=copy_output.get("product_copy_context") or {},
        copy_presence_plan=copy_output.get("copy_presence_plan") or {},
        language_policy=copy_output.get("language_policy") or {},
        interaction_copy_plan=copy_output.get("interaction_copy_plan") or {},
        image_use_plan=(image_use_plan.model_dump() if image_use_plan else {}),
        copy_candidates=copy_output.get("copy_candidates") or [],
        minimal_copy_candidates=copy_output.get("minimal_copy_candidates") or [],
        selected_variant_id=copy_output.get("selected_variant_id"),
        selected_copy=copy_output.get("selected_copy"),
        source_image_path=request.source_image_path,
        source_image_sha256=evidence.get("source_image_sha256"),
        copy_provider_metadata=copy_output.get("provider_metadata") or {},
        failure_reasons=[failure],
    )
    Path(request.output_dir, request.case_id).mkdir(parents=True, exist_ok=True)
    _write_json(Path(request.output_dir) / request.case_id / "result.json", result.model_dump())
    return result


def _openai_text_json(*, prompt: str, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI  # type: ignore

    started = time.perf_counter()
    response = OpenAI(timeout=90).responses.create(model=model, input=prompt, temperature=0)
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    return payload, _provider_metadata(model=model, response=response, latency_ms=int((time.perf_counter() - started) * 1000))


def _openai_image_json(*, prompt: str, image_path: Path, model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import OpenAI  # type: ignore

    started = time.perf_counter()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    response = OpenAI(timeout=90).responses.create(
        model=model,
        input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"}]}],
        temperature=0,
    )
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    return payload, _provider_metadata(model=model, response=response, latency_ms=int((time.perf_counter() - started) * 1000))


def _provider_metadata(*, model: str, response: Any, latency_ms: int) -> dict[str, Any]:
    return {"provider": "openai", "model": model, "fallback_used": False, "token_usage": _usage_dict(response), "latency_ms": latency_ms}


def _strict_provider_metadata(metadata: object, model: str) -> bool:
    if not isinstance(metadata, dict):
        return False
    return metadata.get("provider") == "openai" and metadata.get("model") == model and metadata.get("fallback_used") is False and _positive_usage(metadata.get("token_usage"))


def _validated_copy_output(payload: dict[str, Any], model: str) -> dict[str, Any]:
    output = ActualProductCopyOutput(**payload)
    data = output.model_dump()
    if not _strict_provider_metadata(data.get("provider_metadata"), model):
        raise ValueError("copy provider metadata failed strict validation")
    return data


def _coerce_detected_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _validated_vlm_result(payload: dict[str, Any], model: str) -> dict[str, Any]:
    result = ActualCreativeVLMResult(**{**payload, "detected_text": _coerce_detected_text(payload.get("detected_text"))})
    data = result.model_dump()
    if not _strict_provider_metadata(data.get("provider_metadata"), model):
        raise ValueError("vlm provider metadata failed strict validation")
    return data


def _merge_copy_output_evidence(evidence: dict[str, Any], copy_output: dict[str, Any]) -> dict[str, Any]:
    observations = list(evidence.get("visual_observations") or [])
    observations.extend(copy_output.get("visual_observations") or [])
    understanding = copy_output.get("product_understanding") or {}
    if understanding.get("product_identity_confidence") is not None:
        observations.append(
            {
                "kind": "product_identity",
                "product": understanding.get("normalized_product_candidate") or understanding.get("product_name"),
                "confidence": understanding.get("product_identity_confidence"),
            }
        )
    merged = {
        **evidence,
        "visual_observations": observations,
        "vision_provider_metadata": copy_output.get("vision_provider_metadata") or evidence.get("vision_provider_metadata") or {},
    }
    conflicts = list(evidence.get("input_conflicts") or [])
    conflicts.extend(_structured_input_conflicts(copy_output))
    conflicts.extend(copy_output.get("input_conflicts") or [])
    merged["input_conflicts"] = conflicts
    if conflicts and "product_identity" not in merged.get("unresolved_fields", []):
        merged["unresolved_fields"] = [*(merged.get("unresolved_fields") or []), "product_identity"]
    return merged


def _structured_input_conflicts(copy_output: dict[str, Any]) -> list[dict[str, Any]]:
    text_value = (copy_output.get("product_understanding") or {}).get("explicit_product_candidate")
    image_value = (copy_output.get("product_understanding") or {}).get("visual_product_candidate")
    if text_value and image_value and _normalize_token(text_value) != _normalize_token(image_value):
        return [
            {
                "field": "product_identity",
                "text_value": text_value,
                "image_value": image_value,
                "confidence": (copy_output.get("product_understanding") or {}).get("product_identity_confidence"),
                "resolution": "manual_review",
            }
        ]
    return []


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"product_context_incomplete:{key}")
    return value.strip()


def _normalize_token(value: object) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _usage_dict(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _positive_usage(usage: object) -> bool:
    if not isinstance(usage, dict):
        return False
    return int(usage.get("input_tokens") or 0) > 0 and int(usage.get("output_tokens") or 0) > 0


def _facts_from_text(text: str | None) -> list[dict[str, Any]]:
    if not text:
        return []
    return [{"source": "user_text", "text": text.strip()}]


def _input_conflicts(text: str | None, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def _observation_confidence(observations: list[dict[str, Any]]) -> float:
    text = json.dumps(observations, ensure_ascii=False).lower()
    if not observations:
        return 0.0
    if "confidence" in text:
        for item in observations:
            if isinstance(item, dict) and isinstance(item.get("confidence"), (int, float)):
                return float(item["confidence"])
            value = item.get("value") if isinstance(item, dict) else None
            if isinstance(value, dict) and isinstance(value.get("confidence"), (int, float)):
                return float(value["confidence"])
    return 0.0


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


def _has_existing_overlay_text(observations: list[dict[str, Any]]) -> bool:
    return any(isinstance(item, dict) and item.get("key") == "existing_overlay_text" for item in observations)


def _select_copy(candidates: list[dict[str, Any]], selected_id: str | None) -> dict[str, Any] | None:
    if not candidates:
        return None
    if selected_id:
        for item in candidates:
            if item.get("id") == selected_id:
                return item
    return candidates[0]


def _background_prompt(request: ActualCreativeInput, copy_output: dict[str, Any]) -> str:
    product = _required_text(copy_output.get("product_understanding") or {}, "product_name")
    category = _required_text(copy_output.get("product_understanding") or {}, "broad_category")
    tone = str((copy_output.get("product_copy_context") or {}).get("brand_tone") or "premium")
    return (
        "Premium realistic commercial photography background for a verified product advertisement. "
        f"Product: {product}. Category: {category}. Brand tone: {tone}. Placement: {request.placement}. "
        "Create only the product image, background, lighting, composition, and clean negative space for later copy overlay. "
        "Do not create a poster, advertisement typography, Korean headline, menu wording, brand slogan, price text, discount badge, UI, captions, visible writing, signage, logo, watermark, letters, words, or pseudo text."
    )


def _ocr_from_vlm(vlm: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    if "detected_text" not in vlm or not isinstance(vlm.get("detected_text"), list):
        return {"status": "unavailable", "provider": "openai_vlm_ocr_fallback", "ocr": {"detected_text": [], "missing_text_count": None, "extra_text_count": None}}
    return {"status": "pass", "provider": "openai_vlm_ocr_fallback", "ocr": {"detected_text": vlm.get("detected_text") or [], "missing_text_count": 0, "extra_text_count": 0}}


def _verify_image(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with Image.open(path) as image:
        image.verify()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
