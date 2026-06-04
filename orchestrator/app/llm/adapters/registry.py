"""LLM adapter registry with explicit strict/fallback behavior."""

from __future__ import annotations

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.openai import OpenAIAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import AdapterProvider


class ProviderNotImplementedError(NotImplementedError):
    """Raised when a provider is intentionally not implemented in this milestone."""


def get_llm_adapter(provider: AdapterProvider | str, *, strict: bool = True, allow_mock_fallback: bool = False) -> BaseLLMAdapter:
    if provider == "mock":
        return MockLLMAdapter()
    if provider == "openai":
        return OpenAIAdapter()
    if provider == "openai_compatible":
        return OpenAICompatibleLLMAdapter()
    if provider == "local_openai_compat":
        return LocalOpenAICompatAdapter()
    if allow_mock_fallback:
        return MockLLMAdapter()
    if strict:
        raise ProviderNotImplementedError(f"LLM provider is not implemented: {provider}")
    return MockLLMAdapter()


def get_llm_adapter_safe(provider: AdapterProvider | str, settings: LLMSettings, allow_mock_fallback: bool = True) -> BaseLLMAdapter:
    try:
        return get_llm_adapter(provider, strict=settings.provider_strict_mode, allow_mock_fallback=allow_mock_fallback)
    except ProviderNotImplementedError:
        if allow_mock_fallback:
            return MockLLMAdapter()
        raise
