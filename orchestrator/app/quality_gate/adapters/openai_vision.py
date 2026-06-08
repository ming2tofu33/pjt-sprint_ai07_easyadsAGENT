"""OpenAI API VLM adapter shell.

Actual API calls are opt-in through service routing. This adapter keeps model
selection configurable and avoids storing raw provider responses.
"""

from __future__ import annotations

from orchestrator.app.quality_gate import settings
from orchestrator.app.quality_gate.adapters.openai_compatible_vision import OpenAICompatibleVisionAdapter


class OpenAIVisionAdapter(OpenAICompatibleVisionAdapter):
    provider = "openai"

    def __init__(self, *, model_name: str | None = None, timeout_seconds: int = 30) -> None:
        super().__init__(
            base_url="https://api.openai.com/v1",
            model_name=model_name or settings.get_api_vlm_model(deep=True),
            timeout_seconds=timeout_seconds,
            headers={"Authorization": f"Bearer {settings.get_openai_api_key()}"},
        )
