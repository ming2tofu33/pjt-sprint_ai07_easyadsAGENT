"""MarketingState helpers for the LLM/LangGraph intake graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, NotRequired, TypedDict
from uuid import uuid4

from orchestrator.app.llm.plan_policy import build_default_plan_policy, normalize_user_plan
from orchestrator.app.schemas.llm_marketing import (
    AdFormatSpec,
    ArtifactRef,
    ConversationMessage,
    CopyCandidate,
    CopyGenerationMode,
    CopyModeInferenceOutput,
    CopywritingOutput,
    EntryMode,
    ErrorInfo,
    GeneratedImageCandidate,
    GenerationEngine,
    GenerationRoute,
    ImageFeatures,
    ImageInput,
    ImagePrompt,
    InitialMarketingRequest,
    JobStatus,
    LayoutSpec,
    MarketingContext,
    MarketingCopy,
    MissingField,
    OptionQuestion,
    ProgressState,
    PromptOptimizationOutput,
    PromptRenderOutput,
    ReferenceInput,
    ReferenceStyleSpec,
    RenderProfile,
    TextOverlayConfig,
    ToneBindingOutput,
    UserReadableImageGuide,
    UserSelectionRequest,
    ValidationReport,
    ValidatorOutput,
    T2IRequest,
    T2IResult,
)
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection, PlanPolicy, UserPlan
from orchestrator.app.schemas.text_layout import (
    BackgroundValidationReport,
    CopySpec,
    FinalValidationReport,
    ImagePromptSpec,
    ReadabilityReport,
    RenderResult,
    ResultPayload,
    SafeAreaReport,
    TextLayoutSpec,
    TextStyleSpec,
)

SCHEMA_VERSION = "llm_marketing_v1"
REQUIRED_CONTEXT_FIELDS: list[MissingField] = ["business_type", "item_or_service", "promotion_goal", "ad_format"]
OPTIONAL_CONTEXT_FIELDS: list[MissingField] = ["brand_tone", "target_persona", "region_type", "usp", "time_context"]


class MarketingState(TypedDict, total=False):
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
    model_selections: list[dict[str, Any] | ModelSelection]
    llm_call_results: list[dict[str, Any] | LLMCallResult]
    revision: int
    status: JobStatus
    entry_mode: EntryMode
    generation_route: GenerationRoute
    engine: GenerationEngine
    render_profile: RenderProfile
    progress_state: dict[str, Any] | ProgressState | None
    user_input: str
    prompt_json: dict[str, Any] | None
    messages: list[dict[str, Any] | ConversationMessage]
    conversation_summary: str | None
    current_brief: dict[str, Any]
    dirty_fields: list[str]
    user_selection: dict[str, Any] | UserSelectionRequest | None
    image_input: dict[str, Any] | ImageInput | None
    reference_input: dict[str, Any] | ReferenceInput | None
    source_asset_id: str | None
    reference_asset_id: str | None
    source_image_path: str | None
    reference_image_path: str | None
    input_evidence_bundle: dict[str, Any] | None
    input_normalization_status: str | None
    input_conflicts: list[dict[str, Any]]
    unresolved_questions: list[str]
    product_understanding: dict[str, Any] | None
    product_understanding_status: str | None
    product_understanding_confidence: float | None
    product_understanding_provider_metadata: dict[str, Any] | None
    vision_preprocess_mode: str | None
    selected_reference_template_id: str | None
    selected_reference_template: dict[str, Any] | None
    reference_template_selection: dict[str, Any] | None
    vision_pipeline_results: list[dict[str, Any]]
    image_preprocess_result: dict[str, Any] | None
    image_features: dict[str, Any] | ImageFeatures | None
    reference_style_profile: dict[str, Any] | None
    product_preserve_spec: dict[str, Any] | None
    reference_style: dict[str, Any] | ReferenceStyleSpec | None
    context: dict[str, Any] | MarketingContext
    validator_output: dict[str, Any] | ValidatorOutput | None
    missing_fields: list[MissingField]
    option_question: dict[str, Any] | OptionQuestion | None
    ad_format_spec: dict[str, Any] | AdFormatSpec | None
    layout_spec: dict[str, Any] | LayoutSpec | None
    marketing_copy: dict[str, Any] | MarketingCopy | None
    copywriting_output: dict[str, Any] | CopywritingOutput | None
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
    tone_binding_output: dict[str, Any] | ToneBindingOutput | None
    copy_mode_inference_output: dict[str, Any] | CopyModeInferenceOutput | None
    copy_selection: dict[str, Any] | None
    input_compliance_risk: dict[str, Any] | None
    copy_compliance: list[dict[str, Any]]
    copy_compliance_status: str | None
    copy_compliance_publication_ready: bool
    copy_compliance_gate: dict[str, Any] | None
    copy_compliance_resolution: dict[str, Any] | None
    custom_copy_input: dict[str, Any] | None
    copy_spec: dict[str, Any] | CopySpec | None
    text_layout_spec: dict[str, Any] | TextLayoutSpec | None
    text_style_spec: dict[str, Any] | TextStyleSpec | None
    copy_visual_intent: dict[str, Any] | None
    product_copy_context: dict[str, Any] | None
    copy_presence_plan: dict[str, Any] | None
    language_policy: dict[str, Any] | None
    interaction_copy_plan: dict[str, Any] | None
    minimal_copy_candidates: list[dict[str, Any]]
    selected_minimal_copy_candidate_id: str | None
    typography_art_direction: dict[str, Any] | None
    font_catalog_summary: list[dict[str, Any]]
    adaptive_typography_report: dict[str, Any] | None
    image_layout_analysis: dict[str, Any] | None
    layout_candidate_scores: list[dict[str, Any]]
    layout_refinement_result: dict[str, Any] | None
    layout_copy_fit_report: dict[str, Any] | None
    layout_revision_attempts: int
    image_prompt_spec: dict[str, Any] | ImagePromptSpec | None
    image_prompt: dict[str, Any] | ImagePrompt | None
    prompt_optimization_output: dict[str, Any] | PromptOptimizationOutput | None
    user_readable_image_guide: dict[str, Any] | UserReadableImageGuide | None
    prompt_render_output: dict[str, Any] | PromptRenderOutput | None
    t2i_request: dict[str, Any] | T2IRequest | None
    t2i_result: dict[str, Any] | T2IResult | None
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
    background_validation_report: dict[str, Any] | BackgroundValidationReport | None
    safe_area_report: dict[str, Any] | SafeAreaReport | None
    readability_report: dict[str, Any] | ReadabilityReport | None
    render_result: dict[str, Any] | RenderResult | None
    text_overlay_config: dict[str, Any] | TextOverlayConfig | None
    final_image_path: str | None
    final_validation_report: dict[str, Any] | FinalValidationReport | None
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
    artifact_refs: list[dict[str, Any] | ArtifactRef]
    error_message: str | None
    error_info: dict[str, Any] | ErrorInfo | None
    created_at: str
    updated_at: str
    latency_ms: int | None
    route: NotRequired[GenerationRoute]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    return MarketingContext(**(context or {}))


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
        return "gpt_image_1"
    return "sd35_large"


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
    }
    copy_required = request.copy_generation_mode != "no_copy"
    text_overlay_pending = request.copy_generation_mode != "no_copy"
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
        "messages": [],
        "conversation_summary": None,
        "current_brief": current_brief,
        "dirty_fields": [],
        "user_selection": None,
        "image_input": model_to_dict(request.image_input),
        "reference_input": model_to_dict(request.reference_input),
        "source_asset_id": request.source_asset_id,
        "reference_asset_id": request.reference_asset_id,
        "source_image_path": request.source_image_path,
        "reference_image_path": request.reference_image_path,
        "vision_preprocess_mode": request.vision_preprocess_mode,
        "selected_reference_template_id": request.selected_reference_template_id,
        "selected_reference_template": None,
        "reference_template_selection": None,
        "vision_pipeline_results": [],
        "image_preprocess_result": None,
        "image_features": None,
        "reference_style_profile": None,
        "product_preserve_spec": None,
        "reference_style": None,
        "context": context.model_dump(),
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
    append_message(state, "user", request.user_input)
    state["dirty_fields"] = calculate_dirty_fields(state, list(current_brief))
    return state


def append_message(state: MarketingState, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    state.setdefault("messages", [])
    message = ConversationMessage(role=role, content=content, created_at=now_iso(), metadata=metadata or {})
    state["messages"].append(message.model_dump())
    state["updated_at"] = now_iso()


def append_model_selection(state: MarketingState, selection: dict[str, Any] | ModelSelection) -> None:
    state.setdefault("model_selections", [])
    state["model_selections"].append(model_to_dict(selection))
    state["updated_at"] = now_iso()


def append_llm_call_result(state: MarketingState, result: dict[str, Any] | LLMCallResult) -> None:
    state.setdefault("llm_call_results", [])
    state["llm_call_results"].append(model_to_dict(result))
    state["updated_at"] = now_iso()


def update_current_brief(state: MarketingState, updates: dict[str, Any]) -> None:
    state.setdefault("current_brief", {})
    for key, value in updates.items():
        if value is not None:
            state["current_brief"][key] = value
    state["updated_at"] = now_iso()


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


def set_requested_ad_format(current_brief: dict[str, Any], context_extra: dict[str, Any], value: str) -> None:
    """Write-through setter: keep the two ad_format mirrors consistent.

    current_brief.requested_ad_format is the UI read-model copy;
    context.extra.ad_format is the business-context copy. Writing them
    anywhere else by hand is how they diverged — always use this.
    """
    current_brief["requested_ad_format"] = value
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
