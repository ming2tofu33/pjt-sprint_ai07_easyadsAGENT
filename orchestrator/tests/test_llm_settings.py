from orchestrator.app.llm.settings import LLMSettings, count_api_calls, is_api_call_allowed, model_class_requires_api
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def test_llm_settings_defaults_do_not_enable_api(monkeypatch):
    monkeypatch.delenv("LLM_ENABLE_API_CALL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)
    monkeypatch.delenv("EASYADS_LLM_PROVIDER", raising=False)
    settings = LLMSettings.from_env()

    assert settings.enable_api_call is False
    assert settings.default_provider == "mock"


def test_easyads_llm_settings_aliases(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("EASYADS_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("EASYADS_LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("EASYADS_LLM_API_STYLE", "responses")
    monkeypatch.setenv("EASYADS_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EASYADS_LLM_MAX_RETRIES", "2")

    settings = LLMSettings.from_env()

    assert settings.enable_api_call is True
    assert settings.default_provider == "openai_compatible"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.openai_text_model_mini == "gpt-4o-mini"
    assert settings.llm_base_url == "https://api.example.test/v1"
    assert settings.llm_api_style == "responses"
    assert settings.request_timeout_seconds == 45
    assert settings.max_retries == 2


def test_llm_provider_unknown_falls_back_to_mock(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "unknown")

    settings = LLMSettings.from_env()

    assert settings.default_provider == "mock"


def test_local_llm_settings_are_loaded(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "local_openai_compat")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_API_KEY", "local-dev")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_API_STYLE", "chat_completions")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_TIMEOUT_SECONDS", "60")

    settings = LLMSettings.from_env()

    assert settings.default_provider == "local_openai_compat"
    assert settings.local_llm_provider == "local_openai_compat"
    assert settings.local_llm_base_url == "http://localhost:11434/v1"
    assert settings.local_llm_api_key == "local-dev"
    assert settings.local_llm_model == "gemma4-e4b"
    assert settings.local_llm_api_style == "chat_completions"
    assert settings.local_llm_timeout_seconds == 60


def test_local_llm_model_defaults_to_gemma4_e4b(monkeypatch):
    monkeypatch.delenv("EASYADS_LOCAL_LLM_MODEL", raising=False)

    settings = LLMSettings.from_env()

    assert settings.local_llm_model == "gemma4-e4b"


def test_missing_api_key_does_not_crash_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    settings = LLMSettings.from_env()

    assert settings.openai_api_key is None


def test_cost_guard_blocks_free_and_disabled_api():
    free_selection = ModelSelection(
        node_name="image_prompt_planner",
        user_plan="free",
        selected_model_class="api_nano",
        provider="openai",
        structured_output=True,
        reason="forced api test selection",
    )
    premium_selection = choose_model("image_prompt_planner", "premium")

    assert model_class_requires_api("api_mini") is True
    assert is_api_call_allowed({"plan_policy": {"max_api_calls_per_job": 10}}, free_selection, LLMSettings(enable_api_call=True))[0] is False
    allowed, reason = is_api_call_allowed({"plan_policy": {"max_api_calls_per_job": 10}}, premium_selection, LLMSettings(enable_api_call=False))
    assert allowed is False
    assert reason == "api_call_disabled"


def test_cost_guard_blocks_api_limit():
    selection = choose_model("image_prompt_planner", "premium")
    state = {
        "plan_policy": {"max_api_calls_per_job": 1},
        "llm_call_results": [{"success": True, "model_selection": {"selected_model_class": "api_full"}}],
    }

    assert count_api_calls(state) == 1
    allowed, reason = is_api_call_allowed(state, selection, LLMSettings(enable_api_call=True, openai_api_key="set"))
    assert allowed is False
    assert reason == "api_call_limit_exceeded"
