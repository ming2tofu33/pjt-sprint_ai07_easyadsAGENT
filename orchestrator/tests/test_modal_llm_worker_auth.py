import ast
import sys
import types
from pathlib import Path

from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection(provider: str = "local_openai_compat", model_class: str = "local_quality") -> ModelSelection:
    return ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class=model_class,
        provider=provider,
        structured_output=True,
        reason="test selection",
    )


def test_modal_llm_worker_requires_proxy_auth() -> None:
    source = Path("modal_apps/easyads_llm_worker.py").read_text(encoding="utf-8")
    module = ast.parse(source)

    asgi_app_calls = [
        decorator
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == "serve"
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "asgi_app"
    ]

    assert asgi_app_calls
    assert any(
        keyword.arg == "requires_proxy_auth" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for call in asgi_app_calls
        for keyword in call.keywords
    )


def test_llm_settings_reads_modal_proxy_auth_tokens(monkeypatch) -> None:
    monkeypatch.setenv("EASYADS_MODAL_PROXY_AUTH_TOKEN_ID", "wk-test")
    monkeypatch.setenv("EASYADS_MODAL_PROXY_AUTH_TOKEN_SECRET", "ws-test")

    settings = LLMSettings.from_env()

    assert settings.modal_proxy_auth_token_id == "wk-test"
    assert settings.modal_proxy_auth_token_secret == "ws-test"


def test_local_openai_compat_adapter_sends_modal_proxy_auth_headers(monkeypatch) -> None:
    captured = {}
    openai_module = types.ModuleType("openai")

    class FakeMessage:
        content = "local modal ok"

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
            local_llm_base_url="https://easyads-llm.modal.run/v1",
            local_llm_api_key="local-dev",
            local_llm_model="gemma4-e4b",
            local_llm_api_style="chat_completions",
            modal_proxy_auth_token_id="wk-test",
            modal_proxy_auth_token_secret="ws-test",
        )
    ).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is True
    assert captured["client_kwargs"]["default_headers"] == {
        "Modal-Key": "wk-test",
        "Modal-Secret": "ws-test",
    }
    assert "wk-test" not in str(result.model_dump(mode="json"))
    assert "ws-test" not in str(result.model_dump(mode="json"))
