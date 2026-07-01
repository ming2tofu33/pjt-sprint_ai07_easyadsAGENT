"""Local OpenAI-compatible LLM adapter wrapper."""

from __future__ import annotations

from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.settings import LLMSettings, get_llm_settings


class LocalOpenAICompatAdapter(OpenAICompatibleLLMAdapter):
    provider = "local_openai_compat"

    def __init__(self, settings: LLMSettings | None = None):
        self.local_settings = settings or get_llm_settings()
        super().__init__(
            settings=self.local_settings,
            provider="local_openai_compat",
            provider_profile="local_gemma_e4b",
            base_url=self.local_settings.local_llm_base_url,
            api_key=self.local_settings.local_llm_api_key or "local-dev",
            model=self.local_settings.local_llm_model,
            api_style=self.local_settings.local_llm_api_style,
            timeout_seconds=self.local_settings.local_llm_timeout_seconds,
            max_retries=self.local_settings.local_llm_max_retries,
            default_headers=self.local_settings.modal_proxy_auth_headers(),
        )

    def _preflight(self) -> str | None:
        if not self.settings.enable_api_call:
            return "llm_calls_disabled"
        if not self.local_settings.local_llm_base_url:
            return "local_llm_base_url_missing"
        if not self.local_settings.local_llm_model:
            return "llm_model_not_configured"
        return None
