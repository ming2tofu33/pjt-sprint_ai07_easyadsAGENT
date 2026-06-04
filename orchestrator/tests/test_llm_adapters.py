import sys
import types

from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
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


def test_local_openai_compat_adapter_disabled_guard():
    result = LocalOpenAICompatAdapter(LLMSettings(enable_api_call=False, local_llm_base_url="http://localhost:11434/v1")).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "llm_calls_disabled"
    assert result.metadata["provider"] == "local_openai_compat"
    assert result.metadata["direct_model_load"] is False


def test_local_openai_compat_adapter_requires_base_url():
    result = LocalOpenAICompatAdapter(LLMSettings(enable_api_call=True, local_llm_base_url=None, local_llm_model="gemma4-e4b")).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "local_llm_base_url_missing"


def test_local_openai_compat_adapter_dependency_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = LocalOpenAICompatAdapter(
        LLMSettings(enable_api_call=True, local_llm_base_url="http://localhost:11434/v1", local_llm_model="gemma4-e4b")
    ).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "llm_dependency_unavailable"
    assert "local-dev" not in str(result.model_dump(mode="json"))


def test_local_openai_compat_adapter_uses_chat_completions(monkeypatch):
    captured = {}
    openai_module = types.ModuleType("openai")

    class FakeMessage:
        content = "local smoke ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(choices=[FakeChoice()])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = types.SimpleNamespace(completions=FakeChatCompletions())

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    result = LocalOpenAICompatAdapter(
        LLMSettings(
            enable_api_call=True,
            local_llm_base_url="http://localhost:11434/v1",
            local_llm_api_key="local-dev",
            local_llm_model="gemma4-e4b",
            local_llm_api_style="chat_completions",
        )
    ).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is True
    assert result.output == "local smoke ok"
    assert captured["model"] == "gemma4-e4b"
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["client_kwargs"]["base_url"] == "http://localhost:11434/v1"
    assert "local-dev" not in str(result.model_dump(mode="json"))
