"""LLM runtime settings and API cost guard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orchestrator.app.core.config import _get_bool, _get_env
from orchestrator.app.schemas.llm_model_policy import ModelSelection

ALLOWED_LLM_PROVIDERS = {"mock", "openai", "openai_compatible", "local_openai_compat"}
ALLOWED_LOCAL_LLM_PROVIDERS = {"local_openai_compat", "mock"}


@dataclass(frozen=True)
class LLMSettings:
    enable_api_call: bool = False
    default_provider: str = "mock"
    openai_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_style: str = "responses"
    max_retries: int = 0
    openai_text_model_nano: str | None = None
    openai_text_model_mini: str | None = None
    openai_text_model_full: str | None = None
    openai_vision_model: str | None = None
    max_api_calls_per_job_override: int | None = None
    request_timeout_seconds: int = 30
    provider_strict_mode: bool = True
    local_llm_provider: str = "local_openai_compat"
    local_llm_base_url: str | None = None
    local_llm_api_key: str | None = None
    local_llm_model: str | None = "gemma4-e4b"
    local_llm_api_style: str = "chat_completions"
    local_llm_timeout_seconds: int = 60
    local_llm_max_retries: int = 0

    @classmethod
    def from_env(cls) -> "LLMSettings":
        override = _get_env("LLM_MAX_API_CALLS_PER_JOB_OVERRIDE", "")
        easyads_model = _get_env("EASYADS_LLM_MODEL", "") or None
        easyads_timeout = _get_env("EASYADS_LLM_TIMEOUT_SECONDS", "")
        legacy_timeout = _get_env("LLM_REQUEST_TIMEOUT_SECONDS", "30") or "30"
        max_retries = _get_env("EASYADS_LLM_MAX_RETRIES", "0") or "0"
        local_timeout = _get_env("EASYADS_LOCAL_LLM_TIMEOUT_SECONDS", "60") or "60"
        local_retries = _get_env("EASYADS_LOCAL_LLM_MAX_RETRIES", "0") or "0"
        return cls(
            enable_api_call=_get_bool("EASYADS_ENABLE_LLM_CALLS", _get_bool("LLM_ENABLE_API_CALL", False)),
            default_provider=normalize_llm_provider(_get_env("EASYADS_LLM_PROVIDER", "") or _get_env("LLM_DEFAULT_PROVIDER", "mock")),
            openai_api_key=_get_env("OPENAI_API_KEY", "") or None,
            llm_model=easyads_model,
            llm_base_url=_get_env("EASYADS_LLM_BASE_URL", "") or None,
            llm_api_style=normalize_llm_api_style(_get_env("EASYADS_LLM_API_STYLE", "responses"), default="responses"),
            max_retries=int(max_retries) if max_retries.isdigit() else 0,
            openai_text_model_nano=_get_env("LLM_OPENAI_TEXT_MODEL_NANO", "") or easyads_model,
            openai_text_model_mini=_get_env("LLM_OPENAI_TEXT_MODEL_MINI", "") or easyads_model,
            openai_text_model_full=_get_env("LLM_OPENAI_TEXT_MODEL_FULL", "") or easyads_model,
            openai_vision_model=_get_env("LLM_OPENAI_VISION_MODEL", "") or easyads_model,
            max_api_calls_per_job_override=int(override) if override.isdigit() else None,
            request_timeout_seconds=int(easyads_timeout or legacy_timeout),
            provider_strict_mode=_get_bool("LLM_PROVIDER_STRICT_MODE", True),
            local_llm_provider=normalize_local_llm_provider(_get_env("EASYADS_LOCAL_LLM_PROVIDER", "local_openai_compat")),
            local_llm_base_url=_get_env("EASYADS_LOCAL_LLM_BASE_URL", "") or None,
            local_llm_api_key=_get_env("EASYADS_LOCAL_LLM_API_KEY", "") or None,
            local_llm_model=_get_env("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b") or "gemma4-e4b",
            local_llm_api_style=normalize_llm_api_style(_get_env("EASYADS_LOCAL_LLM_API_STYLE", "chat_completions"), default="chat_completions"),
            local_llm_timeout_seconds=int(local_timeout) if local_timeout.isdigit() else 60,
            local_llm_max_retries=int(local_retries) if local_retries.isdigit() else 0,
        )


def get_llm_settings() -> LLMSettings:
    return LLMSettings.from_env()


def normalize_llm_provider(value: str | None) -> str:
    provider = (value or "mock").strip().lower()
    return provider if provider in ALLOWED_LLM_PROVIDERS else "mock"


def normalize_local_llm_provider(value: str | None) -> str:
    provider = (value or "local_openai_compat").strip().lower()
    return provider if provider in ALLOWED_LOCAL_LLM_PROVIDERS else "local_openai_compat"


def normalize_llm_api_style(value: str | None, *, default: str) -> str:
    style = (value or default).strip().lower()
    return style if style in {"responses", "chat_completions"} else default


def model_class_requires_api(model_class: str) -> bool:
    return model_class.startswith("api_")


def count_api_calls(state: dict[str, Any]) -> int:
    count = 0
    for result in state.get("llm_call_results", []) or []:
        selection = result.get("model_selection") or {}
        if model_class_requires_api(str(selection.get("selected_model_class", ""))):
            count += 1
    return count


def is_api_call_allowed(state: dict[str, Any], model_selection: ModelSelection, settings: LLMSettings) -> tuple[bool, str]:
    if not model_class_requires_api(model_selection.selected_model_class):
        return True, "model class does not require external API"
    if model_selection.user_plan == "free":
        return False, "free_plan_api_disabled"
    if not settings.enable_api_call:
        return False, "api_call_disabled"
    policy = state.get("plan_policy") or {}
    max_calls = settings.max_api_calls_per_job_override
    if max_calls is None:
        max_calls = int(policy.get("max_api_calls_per_job", 0))
    if count_api_calls(state) >= max_calls:
        return False, "api_call_limit_exceeded"
    return True, "api_call_allowed"
