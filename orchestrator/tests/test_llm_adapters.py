import sys

from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection(provider: str = "openai_compatible", model_class: str = "api_mini") -> ModelSelection:
    return ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class=model_class,
        provider=provider,
        structured_output=True,
        reason="test selection",
    )


def test_mock_llm_adapter_returns_deterministic_result():
    result = MockLLMAdapter().invoke_text("hello", _selection(provider="mock", model_class="mock"))

    assert result.success is True
    assert result.output == "mock text response"
    assert result.metadata["mock"] is True


def test_openai_compatible_adapter_does_not_call_when_disabled(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=False, openai_api_key="set", llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_calls_disabled"


def test_openai_compatible_adapter_credentials_missing_when_enabled_without_key():
    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=True, openai_api_key=None, llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_credentials_missing"


def test_openai_compatible_adapter_dependency_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=True, openai_api_key="set", llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_dependency_unavailable"


def test_openai_compatible_adapter_result_does_not_include_api_key():
    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=False, openai_api_key="sk-secret", llm_model="model")).invoke_text(
        "hello",
        _selection(),
        metadata={"api_key": "sk-secret", "safe": True},
    )

    dumped = result.model_dump(mode="json")
    assert "sk-secret" not in str(dumped)
    assert dumped["metadata"]["safe"] is True
