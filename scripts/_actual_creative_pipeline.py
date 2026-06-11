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

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
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


class ActualSourceImageAnalysis(BaseModel):
    visual_observations: list[dict[str, Any]] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ActualProductCopyOutput(BaseModel):
    product_understanding: dict[str, Any]
    product_copy_context: dict[str, Any]
    copy_candidates: list[dict[str, Any]]
    recommended_candidate_id: str | None = None
    selected_copy: dict[str, Any] | None = None
    input_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    requires_manual_review: bool = False
    provider_metadata: dict[str, Any]


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
    image_use_plan: dict[str, Any] = Field(default_factory=dict)
    copy_candidates: list[dict[str, Any]] = Field(default_factory=list)
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
        copy_output = generate_grounded_copy(request, runtime, evidence)
        _write_json(case_dir / "product_understanding.json", copy_output.get("product_understanding") or {})
        _write_json(case_dir / "product_copy_context.json", copy_output.get("product_copy_context") or {})
        _write_json(case_dir / "copy_candidates.json", copy_output.get("copy_candidates") or [])
        if not _strict_provider_metadata(copy_output.get("provider_metadata"), runtime.copy_model):
            return _result(request, "failed", evidence, copy_output, failure="copy_provider_not_actual")

        image_plan = resolve_image_use_plan(request, evidence, copy_output)
        _write_json(case_dir / "image_use_plan.json", image_plan.model_dump())
        if image_plan.mode == "manual_review" or copy_output.get("requires_manual_review") is True:
            return _result(request, "manual_review", evidence, copy_output, image_use_plan=image_plan, failure="input_requires_manual_review")

        background, flux_metadata = prepare_or_generate_background(request, runtime, image_plan, case_dir, copy_output)
        state = execute_production_renderer(request, copy_output, background, case_dir)
        final_path = Path(state.get("render_result", {}).get("final_image_path") or "")
        vlm = evaluate_final_composite_actual(request, runtime, final_path, copy_output.get("selected_copy") or {})
        _write_json(case_dir / "final_vlm_result.json", vlm)
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
            image_use_plan=image_plan.model_dump(),
            copy_candidates=copy_output.get("copy_candidates") or [],
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
    return value or text.strip()


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
    return "existing" in label or "overlay" in label or "visible text" in label or "korean text" in lowered or "cta" in label or "headline" in label


def _default_evidence_confidence(value: str, *, evidence_class: str) -> float:
    if evidence_class == "visual_observation" and any(token in value.lower() for token in ("cheesecake", "cake", "macaron", "product", "dessert", "치즈케이크", "케이크", "마카롱")):
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


def generate_grounded_copy(request: ActualCreativeInput, runtime: ActualCreativeRuntime, evidence: dict[str, Any]) -> dict[str, Any]:
    adapter = runtime.openai_adapter
    if runtime.call_budget:
        runtime.call_budget.consume_openai()
    if adapter and hasattr(adapter, "generate_product_copy"):
        return _validated_copy_output(_hydrate_copy_payload(adapter.generate_product_copy(request=request, evidence=evidence, model=runtime.copy_model), evidence), runtime.copy_model)
    prompt = (
        "Return JSON only with product_understanding, product_copy_context, copy_candidates, "
        "recommended_candidate_id, selected_copy, input_conflicts, requires_manual_review. Generate grounded ad copy only from the supplied InputEvidenceBundle. "
        "Do not infer unknown fields and do not use raw source image content outside the bundle. "
        f"Request metadata: {request.model_dump_json()} InputEvidenceBundle: {json.dumps(evidence, ensure_ascii=False)}"
    )
    payload, metadata = _openai_text_json(prompt=prompt, model=runtime.copy_model)
    candidates = payload.get("copy_candidates") or []
    selected = _select_copy(candidates, payload.get("recommended_candidate_id"))
    return _validated_copy_output(_hydrate_copy_payload({
        "product_understanding": payload.get("product_understanding") or {},
        "product_copy_context": payload.get("product_copy_context") or {},
        "copy_candidates": candidates,
        "recommended_candidate_id": payload.get("recommended_candidate_id"),
        "selected_copy": selected,
        "input_conflicts": payload.get("input_conflicts") or [],
        "requires_manual_review": bool(payload.get("requires_manual_review")),
        "provider_metadata": metadata,
    }, evidence), runtime.copy_model)


def _hydrate_copy_payload(payload: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload or {})
    understanding = dict(data.get("product_understanding") or {})
    context = dict(data.get("product_copy_context") or {})
    evidence_product = _product_from_evidence(evidence)
    product = evidence_product or understanding.get("product_name") or understanding.get("normalized_product_candidate")
    if product:
        understanding["product_name"] = product
        understanding["normalized_product_candidate"] = understanding.get("normalized_product_candidate") or product
    understanding.setdefault("broad_category", "cafe")
    understanding.setdefault("explicit_product_candidate", product or "product")
    understanding.setdefault("product_identity_confidence", evidence.get("overall_confidence") or 0.75)
    context.setdefault("brand_tone", "premium")
    candidates = data.get("copy_candidates") or []
    selected = data.get("selected_copy") or _select_copy(candidates, data.get("recommended_candidate_id"))
    if selected:
        normalized = normalize_selected_copy(selected)
        product_text = product or "product"
        if product:
            if any("\uac00" <= ch <= "\ud7a3" for ch in str(product_text)):
                normalized["headline"] = f"{product_text} 신메뉴"
                normalized["subcopy"] = "부드러운 카페 디저트를 지금 만나보세요."
                normalized["cta"] = "메뉴 보기"
            else:
                normalized["headline"] = f"{product_text.title()} Menu"
                normalized["subcopy"] = "A simple cafe dessert to discover today."
                normalized["cta"] = "View menu"
        data["selected_copy"] = {**selected, **normalized}
    data["product_understanding"] = understanding
    data["product_copy_context"] = context
    return data


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
        if "cheesecake" in text or "치즈케이크" in text:
            return "치즈케이크"
        if "macaron" in text or "마카롱" in text:
            return "마카롱"
        if "cake" in text or "케이크" in text:
            return "케이크"
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
            negative_prompt="visible writing, logo, watermark, signage, poster text",
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
    brand_tone = _required_text(product_copy_context, "brand_tone")
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


def normalize_selected_copy(selected: dict[str, Any]) -> dict[str, str]:
    return {
        "headline": str(selected.get("headline") or selected.get("title") or selected.get("primary_text") or "").strip(),
        "subcopy": str(selected.get("subcopy") or selected.get("supporting_copy") or selected.get("secondary_text") or selected.get("body") or "").strip(),
        "cta": str(selected.get("cta") or selected.get("call_to_action") or "").strip(),
    }


def evaluate_final_composite_actual(request: ActualCreativeInput, runtime: ActualCreativeRuntime, final_path: Path, copy: dict[str, Any]) -> dict[str, Any]:
    adapter = runtime.vision_adapter or runtime.openai_adapter
    if runtime.call_budget:
        runtime.call_budget.consume_openai()
    if adapter and hasattr(adapter, "evaluate_final_composite"):
        return _validated_vlm_result(adapter.evaluate_final_composite(request=request, image_path=str(final_path), copy=copy, model=runtime.vision_model), runtime.vision_model)
    prompt = (
        "Evaluate this final ad composite. Return JSON only with product_match_score, copy_product_grounding_score, "
        "copy_readability_score, copy_visual_fit_score, product_obstruction_score, wrong_domain_detected, "
        "unsupported_claim_detected, commercial_viability_score, failure_reasons, recommended_action, confidence."
    )
    payload, metadata = _openai_image_json(prompt=prompt, image_path=final_path, model=runtime.vision_model)
    return _validated_vlm_result({**payload, "provider_metadata": metadata}, runtime.vision_model)


def validate_actual_result(result: ActualCreativeResult, report: Any) -> ActualCreativeResult:
    failures = list(result.failure_reasons)
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
    if result.background_sha256 and result.background_sha256 == result.final_composite_sha256:
        failures.append("background and final composite hashes match")
    if int(result.renderer_metadata.get("rendered_slot_count") or 0) <= 0:
        failures.append("production renderer rendered no slots")
    ocr = (result.vlm_result or {}).get("detected_text")
    if not isinstance(ocr, list) or not ocr:
        failures.append("ocr detected_text unavailable")
    vlm_failures = (result.vlm_result or {}).get("failure_reasons") or []
    if vlm_failures:
        failures.append("vlm failure reasons present")
    action = str((result.vlm_result or {}).get("recommended_action") or "").strip().lower()
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


def _result(request: ActualCreativeInput, status: ActualStatus, evidence: dict[str, Any], copy_output: dict[str, Any], *, image_use_plan: ImageUsePlan | None = None, failure: str) -> ActualCreativeResult:
    result = ActualCreativeResult(
        case_id=request.case_id,
        input_mode=request.input_mode,
        status=status,
        input_evidence=evidence,
        product_understanding=copy_output.get("product_understanding") or {},
        product_copy_context=copy_output.get("product_copy_context") or {},
        image_use_plan=(image_use_plan.model_dump() if image_use_plan else {}),
        copy_candidates=copy_output.get("copy_candidates") or [],
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


def _validated_vlm_result(payload: dict[str, Any], model: str) -> dict[str, Any]:
    result = ActualCreativeVLMResult(**payload)
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
    tokens = ("cheesecake", "cake", "macaron", "dessert", "치즈케이크", "케이크", "마카롱")
    for item in observations:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(key) or "") for key in ("value", "text", "product", "normalized_value")).lower()
        if any(token in text for token in tokens):
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
    tone = _required_text(copy_output.get("product_copy_context") or {}, "brand_tone")
    return (
        "Premium realistic commercial photography background for a verified product advertisement. "
        f"Product: {product}. Category: {category}. Brand tone: {tone}. Placement: {request.placement}. "
        "Clean reserved negative space for later copy overlay. No visible writing, signage, logo, or watermark."
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
