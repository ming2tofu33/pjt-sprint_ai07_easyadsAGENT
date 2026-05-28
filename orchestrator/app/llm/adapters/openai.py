"""OpenAI adapter skeleton with strict API cost guard behavior."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.settings import LLMSettings, get_llm_settings
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


class OpenAIAdapter(BaseLLMAdapter):
    provider = "openai"

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or get_llm_settings()

    def invoke_structured(
        self,
        schema: Any,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        allowed, error = self._preflight(model_selection)
        if not allowed:
            return self._error(model_selection, error, started, metadata)
        model_name = self._model_name(model_selection)
        if not model_name:
            return self._error(model_selection, "openai_model_not_configured", started, metadata)
        try:
            from openai import OpenAI
        except Exception:
            return self._error(model_selection, "openai_sdk_missing", started, metadata)
        try:
            client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.request_timeout_seconds)
            response = client.responses.create(
                model=model_name,
                input=prompt,
                text={"format": {"type": "json_object"}},
            )
            raw_text = getattr(response, "output_text", None) or ""
            parsed = json.loads(raw_text) if raw_text else {}
            output = self._validate_schema(schema, parsed)
            return LLMCallResult(
                success=True,
                node_name=model_selection.node_name,
                model_selection=model_selection,
                output=output,
                raw_text=raw_text,
                latency_ms=elapsed_ms(started),
                token_usage=None,
                cost_estimate=None,
                metadata={**sanitize_metadata(metadata), "provider": "openai", "model_configured": True},
            )
        except json.JSONDecodeError:
            return self._error(model_selection, "structured_output_parse_failed", started, metadata)
        except Exception as exc:
            return self._error(model_selection, f"openai_api_error:{type(exc).__name__}", started, metadata)

    def invoke_text(
        self,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        allowed, error = self._preflight(model_selection)
        if not allowed:
            return self._error(model_selection, error, started, metadata)
        model_name = self._model_name(model_selection)
        if not model_name:
            return self._error(model_selection, "openai_model_not_configured", started, metadata)
        try:
            from openai import OpenAI
        except Exception:
            return self._error(model_selection, "openai_sdk_missing", started, metadata)
        try:
            client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.request_timeout_seconds)
            response = client.responses.create(model=model_name, input=prompt)
            raw_text = getattr(response, "output_text", None) or ""
            return LLMCallResult(
                success=True,
                node_name=model_selection.node_name,
                model_selection=model_selection,
                output=raw_text,
                raw_text=raw_text,
                latency_ms=elapsed_ms(started),
                cost_estimate=None,
                metadata={**sanitize_metadata(metadata), "provider": "openai", "model_configured": True},
            )
        except Exception as exc:
            return self._error(model_selection, f"openai_api_error:{type(exc).__name__}", started, metadata)

    def invoke_vision(
        self,
        schema: Any,
        image_path: str,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        return self._error(model_selection, "openai_vision_not_implemented", started, {**sanitize_metadata(metadata), "image_path_present": bool(image_path)})

    def _preflight(self, model_selection: ModelSelection) -> tuple[bool, str | None]:
        if not self.settings.enable_api_call:
            return False, "api_call_disabled"
        if not self.settings.openai_api_key:
            return False, "openai_api_key_missing"
        return True, None

    def _model_name(self, model_selection: ModelSelection) -> str | None:
        return {
            "api_nano": self.settings.openai_text_model_nano,
            "api_mini": self.settings.openai_text_model_mini,
            "api_full": self.settings.openai_text_model_full,
            "api_vision": self.settings.openai_vision_model,
        }.get(model_selection.selected_model_class)

    def _validate_schema(self, schema: Any, output: dict[str, Any]) -> dict[str, Any]:
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema(**output).model_dump()
        return output

    def _error(self, model_selection: ModelSelection, error: str | None, started: float, metadata: dict[str, Any] | None) -> LLMCallResult:
        return LLMCallResult(
            success=False,
            node_name=model_selection.node_name,
            model_selection=model_selection,
            output=None,
            raw_text=None,
            error=error or "openai_adapter_error",
            latency_ms=elapsed_ms(started),
            token_usage=None,
            cost_estimate=None,
            metadata={**sanitize_metadata(metadata), "provider": "openai", "api_key_present": bool(self.settings.openai_api_key)},
        )


def elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    safe = dict(metadata or {})
    for key in ("prompt", "api_key", "openai_api_key", "OPENAI_API_KEY"):
        safe.pop(key, None)
    return safe
