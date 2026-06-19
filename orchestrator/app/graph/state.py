"""MarketingState helpers for the LLM/LangGraph intake graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, NotRequired, TypedDict, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from orchestrator.app.llm.plan_policy import build_default_plan_policy, normalize_user_plan
from orchestrator.app.schemas.llm_marketing import (
    ArtifactRef,
    ConversationMessage,
    CopyCandidate,
    CopyGenerationMode,
    EntryMode,
    GeneratedImageCandidate,
    GenerationEngine,
    GenerationRoute,
    InitialMarketingRequest,
    JobStatus,
    MarketingContext,
    MissingField,
    RenderProfile,
)
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection, PlanPolicy, UserPlan

SCHEMA_VERSION = "llm_marketing_v1"
REQUIRED_CONTEXT_FIELDS: list[MissingField] = ["business_type", "item_or_service", "promotion_goal", "ad_format"]
OPTIONAL_CONTEXT_FIELDS: list[MissingField] = ["brand_tone", "target_persona", "region_type", "usp", "time_context"]


class JobMetaState(TypedDict, total=False):
    """Identity, tenancy, routing, plan policy, and run accounting."""
    schema_version: str
    job_id: str
    thread_id: str
    usage_job_db_id: str | None
    usage_thread_db_id: str | None
    workspace_id: str | None
    project_id: str | None
    user_id: str | None
    organization_id: str | None
    user_plan: UserPlan | str
    plan_policy: dict[str, Any] | PlanPolicy
    model_selections: Annotated[list[dict[str, Any] | ModelSelection], append_state_items]
    llm_call_results: Annotated[list[dict[str, Any] | LLMCallResult], append_state_items]
    revision: int
    status: JobStatus
    entry_mode: EntryMode
    generation_route: GenerationRoute
    engine: GenerationEngine
    render_profile: RenderProfile
    progress_state: dict[str, Any] | None


class IntakeState(TypedDict, total=False):
    """User input, conversation/brief, asset inputs, and product understanding."""
    user_input: str
    prompt_json: dict[str, Any] | None
    messages: list[dict[str, Any] | ConversationMessage]
    conversation_summary: str | None
    current_brief: dict[str, Any]
    dirty_fields: list[str]
    confirmed_context_fields: list[str]
    user_selection: dict[str, Any] | None
    image_input: dict[str, Any] | None
    reference_input: dict[str, Any] | None
    source_asset_id: str | None
    reference_asset_id: str | None
    source_image_path: str | None
    reference_image_path: str | None
    input_evidence_bundle: dict[str, Any] | None
    input_normalization_status: str | None
    input_conflicts: list[dict[str, Any]]
    unresolved_questions: list[str]
    intake_understanding_result: dict[str, Any] | None
    intake_extraction_trace: dict[str, Any] | None
    product_understanding: dict[str, Any] | None
    product_understanding_status: str | None
    product_understanding_confidence: float | None
    product_understanding_provider_metadata: dict[str, Any] | None
    vision_preprocess_mode: str | None
    renderer_mode: str | None
    render_options: dict[str, Any] | None


class ReferenceVisionState(TypedDict, total=False):
    """Reference template selection and vision preprocessing artifacts."""
    selected_reference_template_id: str | None
    selected_reference_template: dict[str, Any] | None
    reference_template_selection: dict[str, Any] | None
    vision_pipeline_results: Annotated[list[dict[str, Any]], append_state_items]
    image_preprocess_result: dict[str, Any] | None
    image_features: dict[str, Any] | None
    reference_style_profile: dict[str, Any] | None
    product_preserve_spec: dict[str, Any] | None
    reference_style: dict[str, Any] | None


class ContextValidationState(TypedDict, total=False):
    """Resolved marketing context, validator output, and option questions."""
    context: dict[str, Any] | MarketingContext
    campaign_context: dict[str, Any] | None
    intake_question_policy_decision: dict[str, Any] | None
    validator_output: dict[str, Any] | None
    missing_fields: list[MissingField]
    option_question: dict[str, Any] | None


class CopyState(TypedDict, total=False):
    """Ad format, copy generation, compliance, and copy/text specs."""
    ad_format_spec: dict[str, Any] | None
    layout_spec: dict[str, Any] | None
    marketing_copy: dict[str, Any] | None
    copywriting_output: dict[str, Any] | None
    copy_generation_mode: CopyGenerationMode | None
    copy_candidates: list[dict[str, Any] | CopyCandidate]
    copy_candidate_origin: str | None
    selected_copy_id: str | None
    selected_channel_id: str | None
    selected_ad_format: str | None
    selected_tone: str | None
    custom_direction: str | None
    user_custom_headline: str | None
    user_custom_subcopy: str | None
    copy_required: bool
    text_overlay_pending: bool
    tone_binding_output: dict[str, Any] | None
    copy_mode_inference_output: dict[str, Any] | None
    copy_selection: dict[str, Any] | None
    input_compliance_risk: dict[str, Any] | None
    copy_compliance: list[dict[str, Any]]
    copy_compliance_status: str | None
    copy_compliance_publication_ready: bool
    copy_compliance_gate: dict[str, Any] | None
    copy_compliance_resolution: dict[str, Any] | None
    custom_copy_input: dict[str, Any] | None
    copy_spec: dict[str, Any] | None
    text_layout_spec: dict[str, Any] | None
    text_style_spec: dict[str, Any] | None
    copy_visual_intent: dict[str, Any] | None
    product_copy_context: dict[str, Any] | None
    copy_presence_plan: dict[str, Any] | None
    language_policy: dict[str, Any] | None
    interaction_copy_plan: dict[str, Any] | None
    minimal_copy_candidates: list[dict[str, Any]]
    selected_minimal_copy_candidate_id: str | None


class NativeCreativeState(TypedDict, total=False):
    """GPT-Image native typography single-shot pipeline."""
    creative_execution_plan: dict[str, Any] | None
    native_typography_eligibility: dict[str, Any] | None
    approved_native_copy_brief: dict[str, Any] | None
    format_approved_plan_bundle: dict[str, Any] | None
    flyer_approved_copy_plan: dict[str, Any] | None
    flyer_promotional_approved_copy_plan: dict[str, Any] | None
    product_detail_approved_feature_plan: dict[str, Any] | None
    native_source_visual_analysis: dict[str, Any] | None
    native_creative_prompt_package: dict[str, Any] | None
    native_creative_preflight_review: dict[str, Any] | None
    native_generation_budget: dict[str, Any] | None
    native_generation_result: dict[str, Any] | None
    native_generation_review: dict[str, Any] | None
    native_generation_status: str | None


class TypographyLayoutState(TypedDict, total=False):
    """Typography art direction and layout-fit refinement."""
    typography_art_direction: dict[str, Any] | None
    font_catalog_summary: list[dict[str, Any]]
    adaptive_typography_report: dict[str, Any] | None
    image_layout_analysis: dict[str, Any] | None
    layout_candidate_scores: list[dict[str, Any]]
    layout_refinement_result: dict[str, Any] | None
    layout_copy_fit_report: dict[str, Any] | None
    layout_revision_attempts: int
    poster_layout_spec: dict[str, Any] | None
    image_analysis: dict[str, Any] | None


class ImagePromptT2IState(TypedDict, total=False):
    """Image prompt construction and text-to-image request/result."""
    image_prompt_spec: dict[str, Any] | None
    image_prompt: dict[str, Any] | None
    prompt_optimization_output: dict[str, Any] | None
    user_readable_image_guide: dict[str, Any] | None
    prompt_render_output: dict[str, Any] | None
    t2i_request: dict[str, Any] | None
    t2i_result: dict[str, Any] | None


class QualityGateState(TypedDict, total=False):
    """Quality + OCR gates, regeneration, and image candidates."""
    background_quality_gate: dict[str, Any] | None
    final_quality_gate: dict[str, Any] | None
    quality_gate_attempts: int
    quality_gate_decision: str | None
    quality_gate_status: str | None
    quality_gate_retry_feedback: list[str]
    background_ocr_gate: dict[str, Any] | None
    final_ocr_gate: dict[str, Any] | None
    ocr_gate_decision: str | None
    ocr_gate_status: str | None
    ocr_gate_retry_feedback: list[str]
    ocr_revision_action: str | None
    ocr_revision_attempts: int
    regeneration_patch: dict[str, Any] | None
    candidates: list[dict[str, Any] | GeneratedImageCandidate]
    selected_candidate_id: str | None


class RenderFinalizeState(TypedDict, total=False):
    """Rendering, validation reports, final composite revision, and result."""
    background_validation_report: dict[str, Any] | None
    safe_area_report: dict[str, Any] | None
    readability_report: dict[str, Any] | None
    render_result: dict[str, Any] | None
    text_overlay_config: dict[str, Any] | None
    final_image_path: str | None
    final_validation_report: dict[str, Any] | None
    final_composite_quality_report: dict[str, Any] | None
    final_composite_revision_plan: dict[str, Any] | None
    final_composite_revision_patch: dict[str, Any] | None
    final_composite_retry_feedback: list[str]
    final_composite_partial_rerun: bool
    final_composite_rerun_action: str | None
    reuse_existing_background: bool
    final_copy_revision_result: dict[str, Any] | None
    final_composite_attempts: int
    final_copy_revision_attempts: int
    final_layout_revision_attempts: int
    final_style_revision_attempts: int
    final_background_regeneration_attempts: int
    validation_report: dict[str, Any] | ValidationReport | None
    result_payload: dict[str, Any] | ResultPayload | None
    artifact_refs: Annotated[list[dict[str, Any] | ArtifactRef], append_state_items]
    validation_report: dict[str, Any] | None
    result_payload: dict[str, Any] | None
    artifact_refs: list[dict[str, Any] | ArtifactRef]
    error_message: str | None
    error_info: dict[str, Any] | None
    created_at: str
    updated_at: str
    latency_ms: int | None
    route: NotRequired[GenerationRoute]


class MarketingState(
    JobMetaState,
    IntakeState,
    ReferenceVisionState,
    ContextValidationState,
    CopyState,
    NativeCreativeState,
    TypographyLayoutState,
    ImagePromptT2IState,
    QualityGateState,
    RenderFinalizeState,
    total=False,
):
    """Full LangGraph state — flat at runtime; organized into the sub-state
    groups above for navigability. Composition is by multiple inheritance, so
    ``__annotations__`` is the union of all groups and the runtime shape is the
    same flat dict every node already reads/writes. See docs/state-source-of-truth.md.
    """


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


POSTER_RENDERER_MODE = "poster_components"


def resolve_renderer_mode(
    state: dict[str, Any] | None = None,
    *,
    renderer_mode: str | None = None,
    requested_ad_format: str | None = None,
    ad_format: str | None = None,
    ad_format_spec: dict[str, Any] | None = None,
    selected_reference_template: dict[str, Any] | None = None,
) -> str | None:
    if renderer_mode:
        return renderer_mode

    state = state or {}
    state_renderer_mode = state.get("renderer_mode")
    if state_renderer_mode:
        return str(state_renderer_mode)

    if _is_poster_ad_format(requested_ad_format) or _is_poster_ad_format(ad_format):
        return POSTER_RENDERER_MODE

    current_brief = state.get("current_brief") if isinstance(state, dict) else None
    if isinstance(current_brief, dict):
        if _is_poster_ad_format(current_brief.get("requested_ad_format")):
            return POSTER_RENDERER_MODE
        if _is_poster_ad_format(current_brief.get("ad_format")):
            return POSTER_RENDERER_MODE

    context = state.get("context") if isinstance(state, dict) else None
    if isinstance(context, dict):
        extra = context.get("extra") or {}
        if isinstance(extra, dict) and _is_poster_ad_format(extra.get("ad_format")):
            return POSTER_RENDERER_MODE
    elif isinstance(context, MarketingContext) and _is_poster_ad_format(context.extra.get("ad_format")):
        return POSTER_RENDERER_MODE

    spec_ad_format = _ad_format_from_spec(ad_format_spec or state.get("ad_format_spec"))
    if _is_poster_ad_format(spec_ad_format):
        return POSTER_RENDERER_MODE

    template = selected_reference_template or state.get("selected_reference_template")
    if reference_template_supports_poster(template):
        return POSTER_RENDERER_MODE

    return None


def reference_template_supports_poster(template: Any) -> bool:
    if not template:
        return False
    if hasattr(template, "model_dump"):
        template = template.model_dump()
    if not isinstance(template, dict):
        return False
    ad_formats = template.get("ad_formats") or template.get("adFormats") or []
    if isinstance(ad_formats, str):
        ad_formats = [ad_formats]
    return any(_is_poster_ad_format(value) for value in ad_formats)


def _ad_format_from_spec(spec: Any) -> str | None:
    if not spec:
        return None
    if hasattr(spec, "ad_format"):
        return getattr(spec, "ad_format")
    if hasattr(spec, "model_dump"):
        spec = spec.model_dump()
    if isinstance(spec, dict):
        return spec.get("ad_format") or spec.get("adFormat")
    return None


def _is_poster_ad_format(value: Any) -> bool:
    return str(value or "").strip().lower() == "poster"
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_UNSET = object()


def read_model(
    state: dict[str, Any],
    key: str,
    model_cls: type[_ModelT],
    *,
    default: Any = _UNSET,
) -> _ModelT | None:
    """Read a state field as a Pydantic model — the one coercion entry point.

    State fields are stored as serialized dicts (LangGraph checkpointer needs
    JSON-able state); nodes parse to a model at point of use. This replaces
    ad-hoc `Model(**(state.get(key) or {}))` so the dict|model duality lives
    in exactly one place.

    - Existing model instance is returned untouched (idempotent).
    - Missing/None value: returns an empty `model_cls()` by default, or `None`
      if `default=None` was passed explicitly.
    """
    value = state.get(key)
    if isinstance(value, model_cls):
        return value
    if not value:
        return None if default is None else model_cls()
    return model_cls(**value)


def context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    return read_model({"context": context}, "context", MarketingContext)


def route_for_entry_mode(entry_mode: EntryMode) -> GenerationRoute:
    if entry_mode == "photo_start":
        return "product_composite"
    if entry_mode == "reference_start":
        return "reference_guided_t2i"
    return "text_to_image"


def engine_for_render_profile(render_profile: RenderProfile) -> GenerationEngine:
    if render_profile == "fast":
        return "mock"
    if render_profile == "premium_local":
        return "flux2_klein_4b"
    if render_profile == "premium_api":
        # Legacy render-profile compatibility; public engine selection is validated separately.
        return "gpt_image_1"
    return "sd35_large"


def append_state_items(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    if not right:
        return list(left or [])
    return [*(left or []), *right]


def create_initial_marketing_state(request: InitialMarketingRequest) -> MarketingState:
    timestamp = now_iso()
    job_id = request.job_id or f"job_{uuid4().hex}"
    thread_id = request.thread_id or f"thread_{uuid4().hex}"
    user_plan = normalize_user_plan(request.user_plan)
    plan_policy = build_default_plan_policy(user_plan)
    context = request.context or MarketingContext()
    current_brief: dict[str, Any] = {
        "user_input": request.user_input,
        "requested_ad_format": request.requested_ad_format,
        "requested_platform": request.requested_platform,
        "copy_generation_mode": request.copy_generation_mode,
        # Confirmed only when the user explicitly supplied a mode up front. Heuristic/LLM
        # inference in the validator must NOT flip this true; otherwise the 4-mode question
        # is never asked.
        "copy_generation_mode_confirmed": request.copy_generation_mode is not None,
        "user_custom_headline": request.user_custom_headline,
        "user_custom_subcopy": request.user_custom_subcopy,
        "source_asset_id": request.source_asset_id,
        "reference_asset_id": request.reference_asset_id,
        "source_image_path": request.source_image_path,
        "reference_image_path": request.reference_image_path,
        "selected_reference_template_id": request.selected_reference_template_id,
        "renderer_mode": getattr(request, "renderer_mode", None),
        "requested_template_id": getattr(request, "requested_template_id", None),
        "requested_asset_id": getattr(request, "requested_asset_id", None),
        "advertised_subject": None,
        "advertised_subject_type": None,
        "campaign_intent": None,
        "question_policy_version": None,
    }
    confirmed_context_fields: list[str] = []
    for field in ("business_type", "item_or_service", "promotion_goal", "brand_tone", "target_persona", "region_type"):
        if getattr(context, field, None):
            confirmed_context_fields.append(field)
    if request.requested_ad_format or (context.extra or {}).get("ad_format"):
        confirmed_context_fields.append("ad_format")
    copy_required = request.copy_generation_mode != "no_copy"
    text_overlay_pending = request.copy_generation_mode != "no_copy"
    initial_message = build_message("user", request.user_input)
    state: MarketingState = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "thread_id": thread_id,
        "workspace_id": getattr(request, "workspace_id", None),
        "project_id": request.project_id,
        "user_id": request.user_id,
        "organization_id": request.organization_id,
        "user_plan": user_plan,
        "plan_policy": plan_policy.model_dump(),
        "model_selections": [],
        "llm_call_results": [],
        "revision": 1,
        "status": "input_received",
        "entry_mode": request.entry_mode,
        "generation_route": route_for_entry_mode(request.entry_mode),
        "route": route_for_entry_mode(request.entry_mode),
        "engine": engine_for_render_profile(request.render_profile),
        "render_profile": request.render_profile,
        "progress_state": None,
        "user_input": request.user_input,
        "prompt_json": request.prompt_json,
        "messages": [initial_message],
        "conversation_summary": None,
        "current_brief": current_brief,
        "dirty_fields": [],
        "confirmed_context_fields": confirmed_context_fields,
        "user_selection": None,
        "image_input": model_to_dict(request.image_input),
        "reference_input": model_to_dict(request.reference_input),
        "source_asset_id": request.source_asset_id,
        "reference_asset_id": request.reference_asset_id,
        "source_image_path": request.source_image_path,
        "reference_image_path": request.reference_image_path,
        "input_evidence_bundle": None,
        "input_normalization_status": None,
        "input_conflicts": [],
        "unresolved_questions": [],
        "intake_understanding_result": None,
        "intake_extraction_trace": None,
        "product_understanding": None,
        "product_understanding_status": None,
        "product_understanding_confidence": None,
        "product_understanding_provider_metadata": None,
        "vision_preprocess_mode": request.vision_preprocess_mode,
        "selected_reference_template_id": request.selected_reference_template_id,
        "renderer_mode": getattr(request, "renderer_mode", None),
        "requested_template_id": getattr(request, "requested_template_id", None),
        "requested_asset_id": getattr(request, "requested_asset_id", None),
        "poster_layout_spec": getattr(request, "poster_layout_spec", None),
        "render_options": getattr(request, "render_options", None) or {},
        "selected_reference_template": None,
        "reference_template_selection": None,
        "vision_pipeline_results": [],
        "image_preprocess_result": None,
        "image_features": None,
        "reference_style_profile": None,
        "product_preserve_spec": None,
        "reference_style": None,
        "context": context.model_dump(),
        "campaign_context": None,
        "intake_question_policy_decision": None,
        "validator_output": None,
        "missing_fields": [],
        "option_question": None,
        "ad_format_spec": None,
        "layout_spec": None,
        "marketing_copy": None,
        "copywriting_output": None,
        "copy_generation_mode": request.copy_generation_mode,
        "copy_candidates": [],
        "copy_candidate_origin": None,
        "selected_copy_id": None,
        "selected_channel_id": None,
        "selected_ad_format": None,
        "selected_tone": None,
        "custom_direction": None,
        "user_custom_headline": request.user_custom_headline,
        "user_custom_subcopy": request.user_custom_subcopy,
        "copy_required": copy_required,
        "text_overlay_pending": text_overlay_pending,
        "tone_binding_output": None,
        "copy_mode_inference_output": None,
        "copy_selection": None,
        "input_compliance_risk": None,
        "copy_compliance": [],
        "copy_compliance_status": None,
        "copy_compliance_publication_ready": True,
        "copy_compliance_gate": None,
        "copy_compliance_resolution": None,
        "custom_copy_input": None,
        "copy_spec": None,
        "text_layout_spec": None,
        "text_style_spec": None,
        "copy_visual_intent": None,
        "product_copy_context": None,
        "copy_presence_plan": None,
        "language_policy": None,
        "interaction_copy_plan": None,
        "minimal_copy_candidates": [],
        "selected_minimal_copy_candidate_id": None,
        "creative_execution_plan": None,
        "native_typography_eligibility": None,
        "approved_native_copy_brief": None,
        "format_approved_plan_bundle": None,
        "flyer_approved_copy_plan": None,
        "flyer_promotional_approved_copy_plan": None,
        "product_detail_approved_feature_plan": None,
        "native_source_visual_analysis": None,
        "native_creative_prompt_package": None,
        "native_creative_preflight_review": None,
        "native_generation_budget": None,
        "native_generation_result": None,
        "native_generation_review": None,
        "native_generation_status": None,
        "image_layout_analysis": None,
        "layout_candidate_scores": [],
        "layout_refinement_result": None,
        "layout_copy_fit_report": None,
        "layout_revision_attempts": 0,
        "image_prompt_spec": None,
        "image_prompt": None,
        "prompt_optimization_output": None,
        "user_readable_image_guide": None,
        "prompt_render_output": None,
        "t2i_request": None,
        "t2i_result": None,
        "background_quality_gate": None,
        "final_quality_gate": None,
        "quality_gate_attempts": 0,
        "quality_gate_decision": None,
        "quality_gate_status": None,
        "quality_gate_retry_feedback": [],
        "background_ocr_gate": None,
        "final_ocr_gate": None,
        "ocr_gate_decision": None,
        "ocr_gate_status": None,
        "ocr_gate_retry_feedback": [],
        "ocr_revision_action": None,
        "ocr_revision_attempts": 0,
        "candidates": [],
        "selected_candidate_id": None,
        "background_validation_report": None,
        "safe_area_report": None,
        "readability_report": None,
        "render_result": None,
        "text_overlay_config": None,
        "final_image_path": None,
        "final_validation_report": None,
        "final_composite_quality_report": None,
        "final_composite_revision_plan": None,
        "final_composite_revision_patch": None,
        "final_composite_retry_feedback": [],
        "final_composite_partial_rerun": False,
        "final_composite_rerun_action": None,
        "reuse_existing_background": False,
        "final_copy_revision_result": None,
        "final_composite_attempts": 0,
        "final_copy_revision_attempts": 0,
        "final_layout_revision_attempts": 0,
        "final_style_revision_attempts": 0,
        "final_background_regeneration_attempts": 0,
        "validation_report": None,
        "result_payload": None,
        "artifact_refs": [],
        "error_message": None,
        "error_info": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "latency_ms": None,
    }
    resolved_renderer_mode = resolve_renderer_mode(
        state,
        renderer_mode=getattr(request, "renderer_mode", None),
        requested_ad_format=request.requested_ad_format,
    )
    if resolved_renderer_mode:
        state["renderer_mode"] = resolved_renderer_mode
        current_brief["renderer_mode"] = resolved_renderer_mode

    state["dirty_fields"] = calculate_dirty_fields(state, list(current_brief))
    return state


def build_message(role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return ConversationMessage(role=role, content=content, created_at=now_iso(), metadata=metadata or {}).model_dump()


def append_message(_state: MarketingState, role: str, content: str, metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [build_message(role, content, metadata)]


def append_model_selection(_state: MarketingState, selection: dict[str, Any] | ModelSelection) -> list[dict[str, Any]]:
    return [model_to_dict(selection)]


def append_llm_call_result(_state: MarketingState, result: dict[str, Any] | LLMCallResult) -> list[dict[str, Any]]:
    return [model_to_dict(result)]


def merge_current_brief(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if value is None:
            merged[key] = None
            continue
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
            and key in {"cached_options"}
        ):
            merged[key] = {**merged[key], **value}
            continue
        merged[key] = value
    return merged


def update_current_brief(current_brief: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    return merge_current_brief(current_brief, updates)


def resolve_requested_ad_format(state: dict[str, Any] | MarketingState) -> str | None:
    """Canonical ad_format read order — the single source-of-truth resolver.

    ad_format historically lived in several mirrors with per-reader priority
    orders. All business-logic reads must go through this function:
      1. top-level selected_ad_format (explicit user selection)
      2. current_brief.requested_ad_format (confirmed/restored brief)
      3. context.extra.ad_format (heuristic/LLM inference)
      4. current_brief.ad_format (legacy generic-write key)
    Returns None when unset; callers own their defaults.
    """
    brief = state.get("current_brief") or {}
    context = state.get("context") or {}
    extra = (context.get("extra") if isinstance(context, dict) else getattr(context, "extra", None)) or {}
    for candidate in (
        state.get("selected_ad_format"),
        brief.get("requested_ad_format"),
        extra.get("ad_format"),
        brief.get("ad_format"),
    ):
        if candidate:
            return str(candidate)
    return None


def set_requested_ad_format(
    current_brief: dict[str, Any] | None, context_extra: dict[str, Any] | None, value: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Write-through setter: keep the two ad_format mirrors consistent.

    current_brief.requested_ad_format is the UI read-model copy;
    context.extra.ad_format is the business-context copy. Writing them
    anywhere else by hand is how they diverged — always use this.
    """
    brief = current_brief if isinstance(current_brief, dict) else {}
    extra = context_extra if isinstance(context_extra, dict) else {}
    brief["requested_ad_format"] = value
    extra["ad_format"] = value
    return brief, extra


def backfill_requested_ad_format(
    current_brief: dict[str, Any], context_extra: dict[str, Any], default: str | None
) -> None:
    """Fill missing ad_format mirrors without overwriting an existing choice.

    Priority: an already-set mirror value wins over the supplied default
    (e.g. a reference template's ad_format). Ensures both mirrors end up
    identical — the legacy code filled each independently and could diverge.
    """
    value = current_brief.get("requested_ad_format") or context_extra.get("ad_format") or default
    if not value:
        return
    # Falsy check (not setdefault): initial state seeds the brief key with an
    # explicit None, which must count as "missing" — same rule as the resolver.
    if not current_brief.get("requested_ad_format"):
        current_brief["requested_ad_format"] = value
    if not context_extra.get("ad_format"):
        context_extra["ad_format"] = value


# Declarative dirty-field propagation: (trigger fields, fields invalidated when
# any trigger changes). Single-pass and non-transitive by design — derived
# fields appearing as triggers (e.g. marketing_copy) only fire when explicitly
# listed in changed_fields, mirroring the legacy if-chain.
DIRTY_PROPAGATION_RULES: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"brand_tone", "target_persona", "promotion_goal", "usp", "item_or_service"}),
        frozenset({"marketing_copy", "copywriting_output"}),
    ),
    (
        frozenset({"business_type", "brand_tone", "ad_format", "usp"}),
        frozenset({"image_prompt", "prompt_render_output"}),
    ),
    (
        frozenset({"ad_format"}),
        frozenset({"ad_format_spec", "layout_spec"}),
    ),
    (
        frozenset({"marketing_copy", "copywriting_output", "item_or_service", "promotion_goal", "price_or_discount"}),
        frozenset({"copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"}),
    ),
    (
        frozenset({"brand_tone", "target_persona", "region_type", "usp"}),
        frozenset({"text_style_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"}),
    ),
    (
        frozenset({"ad_format", "layout_spec", "ad_format_spec"}),
        frozenset({"text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"}),
    ),
    (
        frozenset({"copy_generation_mode", "user_custom_headline", "user_custom_subcopy"}),
        frozenset({"marketing_copy", "copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"}),
    ),
)


def calculate_dirty_fields(state: MarketingState, changed_fields: list[str] | None = None) -> list[str]:
    changed = set(changed_fields or [])
    dirty: set[str] = set(changed)
    for triggers, outputs in DIRTY_PROPAGATION_RULES:
        if changed & triggers:
            dirty.update(outputs)
    return sorted(dirty)
