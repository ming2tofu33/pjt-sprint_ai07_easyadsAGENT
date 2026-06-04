from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.adapters.registry import ProviderNotImplementedError, get_llm_adapter
from orchestrator.app.llm.model_router import choose_model, provider_for_model_class
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def test_mock_provider_resolves_to_mock_adapter():
    assert isinstance(get_llm_adapter("mock"), MockLLMAdapter)


def test_openai_compatible_provider_resolves_to_real_adapter_class():
    assert isinstance(get_llm_adapter("openai_compatible"), OpenAICompatibleLLMAdapter)


def test_local_openai_compat_provider_resolves_to_local_adapter():
    assert isinstance(get_llm_adapter("local_openai_compat"), LocalOpenAICompatAdapter)


def test_unknown_provider_falls_back_safely():
    assert isinstance(get_llm_adapter("unknown", strict=False, allow_mock_fallback=True), MockLLMAdapter)


def test_unknown_provider_strict_raises():
    try:
        get_llm_adapter("unknown", strict=True, allow_mock_fallback=False)
    except ProviderNotImplementedError:
        return
    raise AssertionError("expected ProviderNotImplementedError")


def test_legacy_provider_helper_maps_local_models_to_local_openai_compat():
    assert provider_for_model_class("local_fast") == "local_openai_compat"
    assert provider_for_model_class("local_quality") == "local_openai_compat"


def test_free_plan_does_not_select_external_llm_by_default():
    selection = choose_model("image_prompt_planner", "free", confidence=0.1, risk_level="high")

    assert selection.provider != "openai_compatible"
    assert selection.provider != "openai"
    assert not selection.selected_model_class.startswith("api_")


def test_free_plan_local_model_routes_to_local_openai_compat_when_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b")

    selection = choose_model("copy_candidate_generation", "free")

    assert selection.selected_model_class == "local_quality"
    assert selection.provider == "local_openai_compat"
    assert selection.provider_profile == "local_gemma_e4b"
    assert selection.model_name == "gemma4-e4b"
    assert selection.metadata["direct_model_load"] is False


def test_free_plan_local_model_missing_endpoint_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("EASYADS_LOCAL_LLM_BASE_URL", raising=False)

    selection = choose_model("copy_candidate_generation", "free")

    assert selection.provider == "mock"
    assert selection.fallback_used is True
    assert selection.metadata["fallback_reason"] == "local_openai_compat_not_configured"


def test_economic_api_mini_routes_to_openai_provider(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")

    selection = choose_model("copy_candidate_generation", "economic")

    assert selection.selected_model_class == "api_nano"
    assert selection.provider == "openai"


def test_model_selections_shape_is_preserved():
    selection = ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class="api_mini",
        provider="openai_compatible",
        structured_output=True,
        reason="shape preservation",
        metadata={"image_prompt_version": "v3"},
    )

    dumped = selection.model_dump(mode="json")

    assert dumped["node_name"] == "copy_candidate_generation"
    assert dumped["provider"] == "openai_compatible"
    assert dumped["metadata"]["image_prompt_version"] == "v3"
