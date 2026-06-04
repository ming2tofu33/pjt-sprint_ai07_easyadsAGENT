"""Deterministic mock LLM adapter."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from pydantic import BaseModel

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


class MockLLMAdapter(BaseLLMAdapter):
    provider = "mock"

    def invoke_structured(
        self,
        schema: Any,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        output = build_mock_structured_output(schema)
        return self._result(
            model_selection=model_selection,
            output=output,
            latency_ms=elapsed_ms(started),
            metadata={**sanitize_metadata(metadata or {}), "mock": True, "schema_name": getattr(schema, "__name__", str(schema))},
        )

    def invoke_text(
        self,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        return self._result(
            model_selection=model_selection,
            output="mock text response",
            raw_text="mock text response",
            latency_ms=elapsed_ms(started),
            metadata={**sanitize_metadata(metadata or {}), "mock": True},
        )

    def invoke_vision(
        self,
        schema: Any,
        image_path: str,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        output = {"mock": True, "image_path": image_path, "schema_name": getattr(schema, "__name__", str(schema))}
        return self._result(
            model_selection=model_selection,
            output=output,
            latency_ms=elapsed_ms(started),
            metadata={**sanitize_metadata(metadata or {}), "mock": True, "vision": True},
        )

    def _result(
        self,
        model_selection: ModelSelection,
        output: dict[str, Any] | str,
        latency_ms: int,
        metadata: dict[str, Any],
        raw_text: str | None = None,
    ) -> LLMCallResult:
        return LLMCallResult(
            success=True,
            node_name=model_selection.node_name,
            model_selection=model_selection,
            output=output,
            raw_text=raw_text,
            error=None,
            latency_ms=latency_ms,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0},
            cost_estimate=0.0,
            metadata=metadata,
        )


def build_mock_structured_output(schema: Any) -> dict[str, Any]:
    schema_name = getattr(schema, "__name__", str(schema))
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        try:
            return schema().model_dump()
        except Exception:
            return {"mock": True, "schema_name": schema_name}
    return {"mock": True, "schema_name": schema_name}


def elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
