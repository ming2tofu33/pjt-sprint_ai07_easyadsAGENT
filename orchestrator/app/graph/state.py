"""MarketingState helpers for the LLM/LangGraph intake graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, NotRequired, TypedDict
from uuid import uuid4

from orchestrator.app.schemas.llm_marketing import (
    AdFormatSpec,
    ArtifactRef,
    BackgroundValidationReport,
    ConversationMessage,
    CopywritingOutput,
    EntryMode,
    ErrorInfo,
    FinalValidationReport,
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
    UserReadableImageGuide,
    UserSelectionRequest,
    ValidationReport,
    ValidatorOutput,
    T2IRequest,
    T2IResult,
)

SCHEMA_VERSION = "llm_marketing_v1"
REQUIRED_CONTEXT_FIELDS: list[MissingField] = ["business_type", "item_or_service", "promotion_goal", "ad_format"]
OPTIONAL_CONTEXT_FIELDS: list[MissingField] = ["brand_tone", "target_persona", "region_type", "usp", "time_context"]


class MarketingState(TypedDict, total=False):
    schema_version: str
    job_id: str
    thread_id: str
    project_id: str | None
    user_id: str | None
    organization_id: str | None
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
    image_features: dict[str, Any] | ImageFeatures | None
    reference_style: dict[str, Any] | ReferenceStyleSpec | None
    context: dict[str, Any] | MarketingContext
    validator_output: dict[str, Any] | ValidatorOutput | None
    missing_fields: list[MissingField]
    option_question: dict[str, Any] | OptionQuestion | None
    ad_format_spec: dict[str, Any] | AdFormatSpec | None
    layout_spec: dict[str, Any] | LayoutSpec | None
    marketing_copy: dict[str, Any] | MarketingCopy | None
    copywriting_output: dict[str, Any] | CopywritingOutput | None
    image_prompt: dict[str, Any] | ImagePrompt | None
    prompt_optimization_output: dict[str, Any] | PromptOptimizationOutput | None
    user_readable_image_guide: dict[str, Any] | UserReadableImageGuide | None
    prompt_render_output: dict[str, Any] | PromptRenderOutput | None
    t2i_request: dict[str, Any] | T2IRequest | None
    t2i_result: dict[str, Any] | T2IResult | None
    candidates: list[dict[str, Any] | GeneratedImageCandidate]
    selected_candidate_id: str | None
    background_validation_report: dict[str, Any] | BackgroundValidationReport | None
    text_overlay_config: dict[str, Any] | TextOverlayConfig | None
    final_image_path: str | None
    final_validation_report: dict[str, Any] | FinalValidationReport | None
    validation_report: dict[str, Any] | ValidationReport | None
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
        return "flux"
    if render_profile == "premium_api":
        return "gpt_image_2"
    return "sd35_large"


def create_initial_marketing_state(request: InitialMarketingRequest) -> MarketingState:
    timestamp = now_iso()
    job_id = request.job_id or f"job_{uuid4().hex}"
    thread_id = request.thread_id or f"thread_{uuid4().hex}"
    context = request.context or MarketingContext()
    current_brief: dict[str, Any] = {
        "user_input": request.user_input,
        "requested_ad_format": request.requested_ad_format,
        "requested_platform": request.requested_platform,
    }
    state: MarketingState = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "thread_id": thread_id,
        "project_id": request.project_id,
        "user_id": request.user_id,
        "organization_id": request.organization_id,
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
        "image_features": None,
        "reference_style": None,
        "context": context.model_dump(),
        "validator_output": None,
        "missing_fields": [],
        "option_question": None,
        "ad_format_spec": None,
        "layout_spec": None,
        "marketing_copy": None,
        "copywriting_output": None,
        "image_prompt": None,
        "prompt_optimization_output": None,
        "user_readable_image_guide": None,
        "prompt_render_output": None,
        "t2i_request": None,
        "t2i_result": None,
        "candidates": [],
        "selected_candidate_id": None,
        "background_validation_report": None,
        "text_overlay_config": None,
        "final_image_path": None,
        "final_validation_report": None,
        "validation_report": None,
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
    return sorted(dirty)
