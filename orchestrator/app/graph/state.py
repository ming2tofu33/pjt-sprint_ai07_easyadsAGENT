from typing import Any, Literal, NotRequired, TypedDict


JobStatus = Literal[
    "created",
    "validating",
    "waiting_user_selection",
    "refactoring",
    "t2i_queued",
    "t2i_running",
    "overlaying_text",
    "validating_result",
    "done",
    "failed",
]

GenerationEngine = Literal["sd35_large", "flux", "gpt_image_2"]
GenerationRoute = Literal["text_to_image"]


class MarketingState(TypedDict):
    """Shared LangGraph state for the T2I-first marketing banner flow."""

    job_id: str
    status: JobStatus
    route: GenerationRoute
    user_input: str
    prompt_json: NotRequired[dict[str, Any]]
    context: NotRequired[dict[str, Any]]
    validator_output: NotRequired[dict[str, Any]]
    option_question: NotRequired[dict[str, Any]]
    user_selection: NotRequired[dict[str, Any]]
    refactoring_output: NotRequired[dict[str, Any]]
    t2i_request: NotRequired[dict[str, Any]]
    t2i_result: NotRequired[dict[str, Any]]
    text_overlay_config: NotRequired[dict[str, Any]]
    final_image_path: NotRequired[str]
    validation_report: NotRequired[dict[str, Any]]
    engine: NotRequired[GenerationEngine]
    error_message: NotRequired[str | None]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]
    latency_ms: NotRequired[int]

