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
    vision_preprocess_mode: str | None
    selected_reference_template_id: str | None
    selected_reference_template: dict[str, Any] | None
    reference_template_selection: dict[str, Any] | None
    vision_pipeline_results: list[dict[str, Any]]
    image_preprocess_result: dict[str, Any] | None
    image_features: dict[str, Any] | ImageFeatures | None
    image_analysis: dict[str, Any] | None
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
    custom_copy_input: dict[str, Any] | None
    copy_spec: dict[str, Any] | CopySpec | None
    text_layout_spec: dict[str, Any] | TextLayoutSpec | None
    text_style_spec: dict[str, Any] | TextStyleSpec | None
    image_prompt_spec: dict[str, Any] | ImagePromptSpec | None
    image_prompt: dict[str, Any] | ImagePrompt | None
    prompt_optimization_output: dict[str, Any] | PromptOptimizationOutput | None
    user_readable_image_guide: dict[str, Any] | UserReadableImageGuide | None
    prompt_render_output: dict[str, Any] | PromptRenderOutput | None
    t2i_request: dict[str, Any] | T2IRequest | None
    t2i_result: dict[str, Any] | T2IResult | None
    candidates: list[dict[str, Any] | GeneratedImageCandidate]
    selected_candidate_id: str | None
    background_validation_report: dict[str, Any] | BackgroundValidationReport | None
    safe_area_report: dict[str, Any] | SafeAreaReport | None
    readability_report: dict[str, Any] | ReadabilityReport | None
    render_result: dict[str, Any] | RenderResult | None
    text_overlay_config: dict[str, Any] | TextOverlayConfig | None
    final_image_path: str | None
    final_validation_report: dict[str, Any] | FinalValidationReport | None
    validation_report: dict[str, Any] | ValidationReport | None
    result_payload: dict[str, Any] | ResultPayload | None
    artifact_refs: list[dict[str, Any] | ArtifactRef]
    error_message: str | None
    error_info: dict[str, Any] | ErrorInfo | None
    created_at: str
    updated_at: str
    latency_ms: int | None
    rendering_engine: str | None
    renderer_mode: str | None
    requested_template_id: str | None
    requested_asset_id: str | None
    poster_layout_spec: dict[str, Any] | None
    render_options: dict[str, Any] | None
    route: NotRequired[GenerationRoute]


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
    ad_format_spec: dict[str, Any] | AdFormatSpec | None = None,
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
        return "flux"
    if render_profile == "premium_api":
        return "gpt_image_2"
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
        "user_custom_headline": request.user_custom_headline,
        "user_custom_subcopy": request.user_custom_subcopy,
        "source_asset_id": request.source_asset_id if hasattr(request, "source_asset_id") else None,
        "reference_asset_id": request.reference_asset_id if hasattr(request, "reference_asset_id") else None,
        "source_image_path": request.source_image_path,
        "reference_image_path": request.reference_image_path,
        "selected_reference_template_id": request.selected_reference_template_id,
        "renderer_mode": getattr(request, "renderer_mode", None),
        "requested_template_id": getattr(request, "requested_template_id", None),
        "requested_asset_id": getattr(request, "requested_asset_id", None),
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
        "source_asset_id": request.source_asset_id if hasattr(request, "source_asset_id") else None,
        "reference_asset_id": request.reference_asset_id if hasattr(request, "reference_asset_id") else None,
        "source_image_path": request.source_image_path,
        "reference_image_path": request.reference_image_path,
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
        "validator_output": None,
        "missing_fields": [],
        "option_question": None,
        "ad_format_spec": None,
        "layout_spec": None,
        "marketing_copy": None,
        "copywriting_output": None,
        "copy_generation_mode": request.copy_generation_mode,
        "copy_candidates": [],
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
        "custom_copy_input": None,
        "copy_spec": None,
        "text_layout_spec": None,
        "text_style_spec": None,
        "image_prompt_spec": None,
        "image_prompt": None,
        "prompt_optimization_output": None,
        "user_readable_image_guide": None,
        "prompt_render_output": None,
        "t2i_request": None,
        "t2i_result": None,
        "candidates": [],
        "selected_candidate_id": None,
        "background_validation_report": None,
        "safe_area_report": None,
        "readability_report": None,
        "render_result": None,
        "text_overlay_config": None,
        "final_image_path": None,
        "final_validation_report": None,
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


def calculate_dirty_fields(state: MarketingState, changed_fields: list[str] | None = None) -> list[str]:
    changed = set(changed_fields or [])
    dirty: set[str] = set(changed)
    if changed & {"brand_tone", "target_persona", "promotion_goal", "usp", "item_or_service"}:
        dirty.update({"marketing_copy", "copywriting_output"})
    if changed & {"business_type", "brand_tone", "ad_format", "usp"}:
        dirty.update({"image_prompt", "prompt_render_output"})
    if changed & {"ad_format"}:
        dirty.update({"ad_format_spec", "layout_spec"})
    if changed & {"marketing_copy", "copywriting_output", "item_or_service", "promotion_goal", "price_or_discount"}:
        dirty.update({"copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"})
    if changed & {"brand_tone", "target_persona", "region_type", "usp"}:
        dirty.update({"text_style_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"})
    if changed & {"ad_format", "layout_spec", "ad_format_spec"}:
        dirty.update({"text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"})
    if changed & {"copy_generation_mode", "user_custom_headline", "user_custom_subcopy"}:
        dirty.update({"marketing_copy", "copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"})
    return sorted(dirty)
