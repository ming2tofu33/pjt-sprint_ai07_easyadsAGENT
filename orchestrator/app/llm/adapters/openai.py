"""OpenAI adapter skeleton with strict API cost guard behavior."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
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
        raw_text = ""
        try:
            client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.request_timeout_seconds, max_retries=self.settings.max_retries)
            text_format = self._response_format(schema)
            # json_object requires the literal word "json" in the input or it 400s;
            # node prompts don't include it. json_schema carries the field spec itself
            # and has no such requirement. See fix.md #10.
            json_input = (
                prompt
                if text_format["format"]["type"] == "json_schema"
                else prompt + "\n\nReturn only a valid JSON object."
            )
            response = client.responses.create(
                model=model_name,
                input=json_input,
                text=text_format,
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
                token_usage=_usage_dict(response),
                cost_estimate=None,
                metadata={**sanitize_metadata(metadata or {}), "provider": "openai", "model": model_name, "model_configured": True, "retry_count": 0},
            )
        except json.JSONDecodeError:
            return self._error(model_selection, "structured_output_parse_failed", started, metadata, raw_text=raw_text)
        except ValidationError:
            # 모델이 JSON은 줬지만 pydantic 스키마 검증 실패(예: extra 필드, enum/범위 위반).
            # API/네트워크 오류가 아님 → 별도 코드로 분리(과거엔 openai_api_error로 오인). raw_text 보존해 추후 원인 추적. fix.md #16.
            return self._error(model_selection, "structured_output_schema_invalid", started, metadata, raw_text=raw_text)
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
            client = OpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.request_timeout_seconds, max_retries=self.settings.max_retries)
            response = client.responses.create(model=model_name, input=prompt)
            raw_text = getattr(response, "output_text", None) or ""
            return LLMCallResult(
                success=True,
                node_name=model_selection.node_name,
                model_selection=model_selection,
                output=raw_text,
                raw_text=raw_text,
                latency_ms=elapsed_ms(started),
                token_usage=_usage_dict(response),
                cost_estimate=None,
                metadata={**sanitize_metadata(metadata or {}), "provider": "openai", "model": model_name, "model_configured": True, "retry_count": 0},
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
        return self._error(model_selection, "openai_vision_not_implemented", started, {**sanitize_metadata(metadata or {}), "image_path_present": bool(image_path)})

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

    def _response_format(self, schema: Any) -> dict[str, Any]:
        # Pydantic schema -> json_schema so the model returns the exact field names
        # (otherwise it invents plausible ad fields and _validate_schema raises).
        # strict=False because OpenAI strict=True rejects pydantic schemas that lack
        # additionalProperties:false on every object. Non-pydantic -> json_object.
        # See fix.md #10.
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return {
                "format": {
                    "type": "json_schema",
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": False,
                }
            }
        return {"format": {"type": "json_object"}}

    def _error(self, model_selection: ModelSelection, error: str | None, started: float, metadata: dict[str, Any] | None, raw_text: str | None = None) -> LLMCallResult:
        # raw_text: 스키마 검증/파싱 실패 시 모델 원문(앞 500자)을 보존 → 어떤 필드가 깨졌는지 추후 확인.
        # sanitize_metadata가 prompt/api_key는 지우지만 raw_text는 모델 출력이라 안 지움.
        snippet = raw_text[:500] if raw_text else None
        return LLMCallResult(
            success=False,
            node_name=model_selection.node_name,
            model_selection=model_selection,
            output=None,
            raw_text=snippet,
            error=error or "openai_adapter_error",
            latency_ms=elapsed_ms(started),
            token_usage=None,
            cost_estimate=None,
            metadata={**sanitize_metadata(metadata or {}), "provider": "openai", "api_key_present": bool(self.settings.openai_api_key), "raw_output_present": bool(raw_text), "raw_output_length": len(raw_text) if raw_text else 0, "retry_count": 0},
        )


def elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _usage_dict(response: Any) -> dict[str, int] | None:
    """Extract token counts from a Responses API result so real USD cost can be
    computed (pricing reads input_tokens/output_tokens/cached_tokens). See fix.md #6.
    Returns None when usage is absent (cost stays unmeasured, never fabricated)."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    def _int(obj: Any, name: str) -> int | None:
        val = getattr(obj, name, None)
        return val if isinstance(val, int) else None

    details = getattr(usage, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    return {
        "input_tokens": _int(usage, "input_tokens"),
        "output_tokens": _int(usage, "output_tokens"),
        "total_tokens": _int(usage, "total_tokens"),
        "cached_tokens": cached if isinstance(cached, int) else 0,
    }

