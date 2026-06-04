from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.adapters.registry import get_llm_adapter
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def test_mock_provider_resolves_to_mock_adapter():
    assert isinstance(get_llm_adapter("mock"), MockLLMAdapter)


def test_openai_compatible_provider_resolves_to_real_adapter_class():
    assert isinstance(get_llm_adapter("openai_compatible"), OpenAICompatibleLLMAdapter)


def test_unknown_provider_falls_back_safely():
    assert isinstance(get_llm_adapter("unknown", strict=False, allow_mock_fallback=True), MockLLMAdapter)


def test_free_plan_does_not_select_external_llm_by_default():
    selection = choose_model("image_prompt_planner", "free", confidence=0.1, risk_level="high")

    assert selection.provider != "openai_compatible"
    assert selection.provider != "openai"
    assert not selection.selected_model_class.startswith("api_")


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
