"""LLM adapter registry with safe mock fallback."""

from __future__ import annotations

from orchestrator.app.llm.adapters.base import BaseLLMAdapter
from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.schemas.llm_model_policy import AdapterProvider


def get_llm_adapter(provider: AdapterProvider | str) -> BaseLLMAdapter:
    if provider == "mock":
        return MockLLMAdapter()
    # API/local providers intentionally fall back to mock in this skeleton.
    return MockLLMAdapter()
