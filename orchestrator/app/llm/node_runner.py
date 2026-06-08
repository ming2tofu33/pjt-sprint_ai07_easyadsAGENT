"""Shared guarded runner for optional structured LLM node calls."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from orchestrator.app.core.config import _get_env
from orchestrator.app.llm.adapters.registry import get_llm_adapter_safe
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.settings import LLMSettings, get_llm_settings, is_api_call_allowed
from orchestrator.app.schemas.llm_model_policy import LLMCallResult
from orchestrator.app.usage import service as usage_service


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

    # TEMPORARY (free → local Gemma for eval). Normally free returns the deterministic
    # fallback here (decision step 1). When EASYADS_FREE_USE_LOCAL=1 AND the router picked
    # a self-hosted provider (local Gemma via local_openai_compat), let the call through so
    # the free tier exercises the local model. API/mock providers still fall back, so a free
    # job can never reach a paid API. Revert: unset the env / delete this block.
    # See fix.md #14, updates.md. SD3.5 T2I deferred (fix.md #7).
    _is_free = state.get("user_plan", "free") == "free"
    _free_local = (
        _is_free
        and _get_env("EASYADS_FREE_USE_LOCAL", "") == "1"
        and selection.provider in {"local_openai_compat", "local_gemma", "local_qwen"}
    )
    if _is_free and not _free_local:
        return fallback_with_result(state, selection, fallback_fn, "free_plan_deterministic_fallback", metadata)
    if selection.selected_model_class.startswith("api_") and not settings.enable_api_call:
        return fallback_with_result(state, selection, fallback_fn, "api_call_disabled", metadata)

    allowed, guard_reason = is_api_call_allowed(state, selection, settings)
    if not allowed:
        return fallback_with_result(state, selection, fallback_fn, guard_reason, metadata)
    if selection.provider == "mock":
        return fallback_with_result(state, selection, fallback_fn, "provider_mock_fallback", metadata)

    adapter = get_llm_adapter_safe(selection.provider, settings, allow_mock_fallback=True)
    result = adapter.invoke_structured(output_schema, prompt, selection, metadata=safe_metadata(metadata))
    record_llm_usage_from_result(state, result)
    append_llm_call_result(state, result)
    if result.success:
        try:
            output = validate_output(output_schema, result.output)
            return output, {
                "llm_attempted": True,
                "fallback_used": False,
                "model_selection": selection.model_dump(),
                "llm_call_result": safe_llm_call_result(result),
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
        "llm_call_result": safe_llm_call_result(result),
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
    sanitized = sanitize_metadata(safe)
    return sanitized if isinstance(sanitized, dict) else {}


def append_model_selection(state: dict[str, Any], selection: Any) -> None:
    state.setdefault("model_selections", [])
    state["model_selections"].append(selection.model_dump() if hasattr(selection, "model_dump") else selection)


def append_llm_call_result(state: dict[str, Any], result: Any) -> None:
    state.setdefault("llm_call_results", [])
    state["llm_call_results"].append(safe_llm_call_result(result))


def record_llm_usage_from_result(state: dict[str, Any], result: Any) -> None:
    if not getattr(result, "success", False) and not getattr(result, "token_usage", None):
        return
    selection = getattr(result, "model_selection", None)
    provider = getattr(selection, "provider", None)
    if provider in {None, "mock"}:
        return
    workspace_id = state.get("workspace_id")
    if not workspace_id:
        return
    token_usage = getattr(result, "token_usage", None) or {}
    try:
        usage_service.record_llm_usage(
            workspace_id=str(workspace_id),
            provider=str(provider),
            model_name=str(getattr(selection, "model_name", None) or getattr(selection, "provider_profile", None) or getattr(selection, "selected_model_class", "")),
            plan=str(state.get("user_plan") or "free"),
            input_tokens=token_usage.get("input_tokens"),
            output_tokens=token_usage.get("output_tokens"),
            total_tokens=token_usage.get("total_tokens"),
            cached_input_tokens=token_usage.get("cached_tokens") or token_usage.get("cached_input_tokens"),
            created_by=state.get("user_id"),
            thread_id=state.get("thread_id"),
            job_id=state.get("job_id"),
            task_name=getattr(selection, "node_name", None),
            node_name=getattr(selection, "node_name", None),
            provider_request_id=(getattr(result, "metadata", None) or {}).get("provider_request_id"),
            request_status="succeeded" if getattr(result, "success", False) else "failed",
        )
    except Exception:
        state.setdefault("usage_recording_warnings", []).append({"event_type": "llm_call", "reason": "usage_record_failed"})


def safe_llm_call_result(result: Any) -> dict[str, Any]:
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result or {})
    selection = data.get("model_selection") or {}
    output = data.get("output")
    if isinstance(output, dict):
        output_count = len(output.get("candidates") or [])
    elif isinstance(output, list):
        output_count = len(output)
    else:
        output_count = 1 if output else 0
    return {
        "success": data.get("success"),
        "node_name": data.get("node_name"),
        "provider": selection.get("provider"),
        "selected_model_class": selection.get("selected_model_class"),
        "model_name": selection.get("model_name"),
        "provider_profile": selection.get("provider_profile"),
        "latency_ms": data.get("latency_ms"),
        "error": data.get("error"),
        "raw_text_present": bool(data.get("raw_text")),
        "output_candidate_count": output_count,
        "metadata": safe_metadata(data.get("metadata") or {}),
    }
