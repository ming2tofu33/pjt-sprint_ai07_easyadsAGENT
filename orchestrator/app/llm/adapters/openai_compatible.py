"""Guarded OpenAI-compatible LLM adapter."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.adapters.openai import (
    CALL_INSTRUCTION_METADATA_KEY_SET,
    CALL_INSTRUCTION_METADATA_KEYS,
    DEFAULT_SYSTEM_INSTRUCTION,
    _pydantic_json_invalid,
    _strict_json_schema,
)
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
from orchestrator.app.llm.settings import LLMSettings, get_llm_settings
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


class OpenAICompatibleLLMAdapter(BaseLLMAdapter):
    provider = "openai_compatible"

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        provider: str = "openai_compatible",
        provider_profile: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        api_style: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        default_headers: dict[str, str] | None = None,
    ):
        self.settings = settings or get_llm_settings()
        self.provider = provider
        self.provider_profile = provider_profile
        self.base_url = base_url if base_url is not None else self.settings.llm_base_url
        self.api_key = api_key if api_key is not None else self.settings.openai_api_key
        self.model = model if model is not None else self.settings.llm_model
        self.api_style = api_style or self.settings.llm_api_style
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else self.settings.request_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else self.settings.max_retries
        self.default_headers = dict(default_headers or {})

    def invoke_structured(
        self,
        schema: Any,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        preflight_error = self._preflight()
        if preflight_error:
            return self._error(model_selection, preflight_error, started, metadata)
        model_name = self._model_name(model_selection)
        if not model_name:
            return self._error(model_selection, "llm_model_not_configured", started, metadata)
        try:
            from openai import OpenAI  # type: ignore
        except Exception:
            return self._error(model_selection, "llm_dependency_unavailable", started, metadata)
        try:
            client_kwargs = {"api_key": self.api_key, "timeout": self.timeout_seconds}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            if self.default_headers:
                client_kwargs["default_headers"] = self.default_headers
            client = OpenAI(**client_kwargs)
            raw_text = self._create_structured_response_text(client, model_name, prompt, schema, metadata)
            output = self._parse_structured_output(schema, raw_text)
            return self._success(model_selection, output, raw_text, started, metadata, model_name)
        except json.JSONDecodeError:
            return self._error(model_selection, "llm_structured_output_parse_failed", started, metadata)
        except ValidationError as exc:
            error_code = (
                "llm_structured_output_parse_failed"
                if _pydantic_json_invalid(exc)
                else "llm_structured_output_schema_invalid"
            )
            return self._error(model_selection, error_code, started, metadata)
        except Exception as exc:
            return self._error(model_selection, f"llm_api_error:{type(exc).__name__}", started, metadata)

    def invoke_text(
        self,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        preflight_error = self._preflight()
        if preflight_error:
            return self._error(model_selection, preflight_error, started, metadata)
        model_name = self._model_name(model_selection)
        if not model_name:
            return self._error(model_selection, "llm_model_not_configured", started, metadata)
        try:
            from openai import OpenAI  # type: ignore
        except Exception:
            return self._error(model_selection, "llm_dependency_unavailable", started, metadata)
        try:
            client_kwargs = {"api_key": self.api_key, "timeout": self.timeout_seconds}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            if self.default_headers:
                client_kwargs["default_headers"] = self.default_headers
            client = OpenAI(**client_kwargs)
            raw_text = self._create_text_response_text(client, model_name, prompt, metadata)
            return self._success(model_selection, raw_text, raw_text, started, metadata, model_name)
        except Exception as exc:
            return self._error(model_selection, f"llm_api_error:{type(exc).__name__}", started, metadata)

    def invoke_vision(
        self,
        schema: Any,
        image_path: str,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        started = perf_counter()
        return self._error(
            model_selection,
            "llm_vision_not_implemented",
            started,
            {**self._result_metadata(metadata), "image_path_present": bool(image_path)},
        )

    def _preflight(self) -> str | None:
        if not self.settings.enable_api_call:
            return "llm_calls_disabled"
        if not self.api_key:
            return "llm_credentials_missing"
        return None

    def _model_name(self, model_selection: ModelSelection) -> str | None:
        if self.model:
            return self.model
        return {
            "api_nano": self.settings.openai_text_model_nano,
            "api_mini": self.settings.openai_text_model_mini,
            "api_full": self.settings.openai_text_model_full,
            "api_vision": self.settings.openai_vision_model,
        }.get(model_selection.selected_model_class)

    def _create_text_response_text(
        self,
        client: Any,
        model_name: str,
        prompt: str,
        metadata: dict[str, Any] | None,
    ) -> str:
        instructions, user_input = self._call_context(prompt, metadata)
        if self.api_style == "chat_completions":
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user_input},
                ],
            )
            return self._chat_completion_text(response)
        response = client.responses.create(model=model_name, instructions=instructions, input=user_input)
        return getattr(response, "output_text", None) or ""

    def _create_structured_response_text(
        self,
        client: Any,
        model_name: str,
        prompt: str,
        schema: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        # Prefer json_schema (constrained decoding) over json_object: local servers (Ollama)
        # enforce the schema so output validates; falls back to json_object when no schema.
        # OpenAI-compat servers that reject json_schema raise → invoke_structured except → node fallback.
        chat_format = self._json_response_format(schema)
        instructions, user_input = self._call_context(
            prompt,
            metadata,
            force_json_object=chat_format.get("type") == "json_object",
        )
        if self.api_style == "chat_completions":
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user_input},
                ],
                response_format=chat_format,
            )
            return self._chat_completion_text(response)
        # responses API: format goes under text.format with the same shape sans the wrapping key
        if chat_format.get("type") == "json_object":
            text_format = chat_format
        else:
            json_schema = chat_format["json_schema"]
            text_format = {
                "type": "json_schema",
                "name": json_schema["name"],
                "schema": json_schema["schema"],
                "strict": json_schema.get("strict", True),
            }
        response = client.responses.create(
            model=model_name,
            instructions=instructions,
            input=user_input,
            text={"format": text_format},
        )
        return getattr(response, "output_text", None) or ""

    @staticmethod
    def _json_response_format(schema: Any) -> dict[str, Any]:
        json_schema = None
        if schema is not None and hasattr(schema, "model_json_schema"):
            try:
                json_schema = schema.model_json_schema()
            except Exception:
                json_schema = None
        if not json_schema:
            return {"type": "json_object"}
        name = getattr(schema, "__name__", "structured_output")
        return {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "schema": _strict_json_schema(json_schema),
                "strict": True,
            },
        }

    def _chat_completion_text(self, response: Any) -> str:
        try:
            return response.choices[0].message.content or ""
        except Exception:
            return ""

    def _parse_structured_output(self, schema: Any, raw_text: str) -> dict[str, Any]:
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate_json(raw_text or "{}").model_dump()
        return json.loads(raw_text) if raw_text else {}

    def _call_context(
        self,
        prompt: str,
        metadata: dict[str, Any] | None,
        force_json_object: bool = False,
    ) -> tuple[str, str]:
        instructions = self._system_instruction(metadata)
        if force_json_object:
            instructions = f"{instructions}\nReturn only a valid JSON object."
        return instructions, prompt

    def _system_instruction(self, metadata: dict[str, Any] | None) -> str:
        metadata = metadata or {}
        for key in CALL_INSTRUCTION_METADATA_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return DEFAULT_SYSTEM_INSTRUCTION

    def _result_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        cleaned = {
            key: value
            for key, value in (metadata or {}).items()
            if str(key).lower() not in CALL_INSTRUCTION_METADATA_KEY_SET
        }
        sanitized = sanitize_metadata(cleaned)
        return sanitized if isinstance(sanitized, dict) else {}

    def _success(
        self,
        model_selection: ModelSelection,
        output: dict[str, Any] | str,
        raw_text: str | None,
        started: float,
        metadata: dict[str, Any] | None,
        model_name: str,
    ) -> LLMCallResult:
        return LLMCallResult(
            success=True,
            node_name=model_selection.node_name,
            model_selection=model_selection,
            output=output,
            raw_text=raw_text,
            error=None,
            latency_ms=elapsed_ms(started),
            token_usage=None,
            cost_estimate=None,
            metadata={
                **self._result_metadata(metadata),
                "provider": self.provider,
                "provider_profile": self.provider_profile,
                "model": model_name,
                "api_style": self.api_style,
                "model_configured": bool(model_name),
                "base_url_configured": bool(self.base_url),
                "api_key_present": bool(self.api_key),
                "direct_model_load": False,
            },
        )

    def _error(
        self,
        model_selection: ModelSelection,
        error: str,
        started: float,
        metadata: dict[str, Any] | None,
    ) -> LLMCallResult:
        return LLMCallResult(
            success=False,
            node_name=model_selection.node_name,
            model_selection=model_selection,
            output=None,
            raw_text=None,
            error=error,
            latency_ms=elapsed_ms(started),
            token_usage=None,
            cost_estimate=None,
            metadata={
                **self._result_metadata(metadata),
                "provider": self.provider,
                "provider_profile": self.provider_profile,
                "api_style": self.api_style,
                "model_configured": bool(self.model),
                "base_url_configured": bool(self.base_url),
                "api_key_present": bool(self.api_key),
                "direct_model_load": False,
            },
        )


def elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
