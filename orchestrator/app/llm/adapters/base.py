"""Base interface for future LLM adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


class BaseLLMAdapter(ABC):
    provider: str

    @abstractmethod
    def invoke_structured(
        self,
        schema: Any,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        """Invoke a model and return schema-aligned output."""

    @abstractmethod
    def invoke_text(
        self,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        """Invoke a model and return plain text output."""

    @abstractmethod
    def invoke_vision(
        self,
        schema: Any,
        image_path: str,
        prompt: str,
        model_selection: ModelSelection,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallResult:
        """Invoke a vision-capable model and return schema-aligned output."""
