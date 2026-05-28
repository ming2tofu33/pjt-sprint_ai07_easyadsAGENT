"""Shared guarded runner for optional structured LLM node calls."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from orchestrator.app.llm.adapters.registry import get_llm_adapter_safe
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.settings import LLMSettings, get_llm_settings, is_api_call_allowed
from orchestrator.app.schemas.llm_model_policy import LLMCallResult


FallbackFn = Callable[[], Any]


def run_structured_node(
    state: dict[str, Any],
    node_name: str,
    output_schema: Any,
    prompt: str,
    fallback_fn: FallbackFn,
    risk_level: str = "medium",
    confidence: float | None = None,
    latency_budget: str = "interactive",
    vision_required: bool = False,
    metadata: dict[str, Any] | None = None,
    settings: LLMSettings | None = None,
) -> tuple[Any, dict[str, Any]]:
    settings = settings or get_llm_settings()
    selection = choose_model(
        node_name=node_name,
        user_plan=state.get("user_plan", "free"),
        confidence=confidence,
        risk_level=risk_level,
        latency_budget=latency_budget,
        vision_required=vision_required,
        plan_policy=state.get("plan_policy"),
    )
    append_model_selection(state, selection)

    if state.get("user_plan", "free") == "free":
        return fallback_with_result(state, selection, fallback_fn, "free_plan_deterministic_fallback", metadata)
    if selection.selected_model_class.startswith("api_") and not settings.enable_api_call:
        return fallback_with_result(state, selection, fallback_fn, "api_call_disabled", metadata)

    allowed, guard_reason = is_api_call_allowed(state, selection, settings)
    if not allowed:
        return fallback_with_result(state, selection, fallback_fn, guard_reason, metadata)

    adapter = get_llm_adapter_safe(selection.provider, settings, allow_mock_fallback=True)
    result = adapter.invoke_structured(output_schema, prompt, selection, metadata=safe_metadata(metadata))
    append_llm_call_result(state, result)
    if result.success:
        try:
            output = validate_output(output_schema, result.output)
            return output, {
                "llm_attempted": True,
                "fallback_used": False,
                "model_selection": selection.model_dump(),
                "llm_call_result": result.model_dump(),
            }
        except Exception:
            return fallback_with_result(state, selection, fallback_fn, "structured_output_validation_failed", metadata, attempted_result=result)
    return fallback_with_metadata(selection, fallback_fn, result.error or "llm_call_failed", result)


def fallback_with_result(
    state: dict[str, Any],
    selection,
    fallback_fn: FallbackFn,
    reason: str,
    metadata: dict[str, Any] | None,
    attempted_result: LLMCallResult | None = None,
) -> tuple[Any, dict[str, Any]]:
    result = attempted_result or LLMCallResult(
        success=False,
        node_name=selection.node_name,
        model_selection=selection,
        output=None,
        error=reason,
        latency_ms=0,
        token_usage=None,
        cost_estimate=0.0,
        metadata={**safe_metadata(metadata), "fallback_used": True, "fallback_reason": reason},
    )
    if attempted_result is None:
        append_llm_call_result(state, result)
    return fallback_with_metadata(selection, fallback_fn, reason, result)


def fallback_with_metadata(selection, fallback_fn: FallbackFn, reason: str, result: LLMCallResult) -> tuple[Any, dict[str, Any]]:
    return fallback_fn(), {
        "llm_attempted": result.error not in {"api_call_disabled", "free_plan_deterministic_fallback"},
        "fallback_used": True,
        "fallback_reason": reason,
        "provider": selection.provider,
        "selected_model_class": selection.selected_model_class,
        "node_name": selection.node_name,
        "model_selection": selection.model_dump(),
        "llm_call_result": result.model_dump(),
    }


def validate_output(output_schema: Any, output: Any) -> Any:
    if isinstance(output_schema, type) and issubclass(output_schema, BaseModel):
        if isinstance(output, output_schema):
            return output
        return output_schema(**(output or {}))
    return output


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    safe = dict(metadata or {})
    safe.pop("prompt", None)
    safe.pop("openai_api_key", None)
    return safe


def append_model_selection(state: dict[str, Any], selection: Any) -> None:
    state.setdefault("model_selections", [])
    state["model_selections"].append(selection.model_dump() if hasattr(selection, "model_dump") else selection)


def append_llm_call_result(state: dict[str, Any], result: Any) -> None:
    state.setdefault("llm_call_results", [])
    state["llm_call_results"].append(result.model_dump() if hasattr(result, "model_dump") else result)
