from orchestrator.app.llm.adapters.openai import OpenAIAdapter
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection(model_class: str = "api_mini") -> ModelSelection:
    return ModelSelection(
        node_name="auto_pilot_copywriting",
        user_plan="premium",
        selected_model_class=model_class,
        provider="openai",
        structured_output=True,
        reason="test selection",
    )


def test_openai_adapter_disabled_returns_error_without_import():
    result = OpenAIAdapter(LLMSettings(enable_api_call=False)).invoke_text("hello", _selection(), metadata={"prompt": "secret", "openai_api_key": "secret"})

    assert result.success is False
    assert result.error == "api_call_disabled"
    assert result.metadata["api_key_present"] is False
    assert "secret" not in str(result.metadata)


def test_openai_adapter_key_missing_returns_error():
    result = OpenAIAdapter(LLMSettings(enable_api_call=True, openai_api_key=None, openai_text_model_mini="model")).invoke_text("hello", _selection())

    assert result.success is False
    assert result.error == "openai_api_key_missing"


def test_openai_adapter_model_missing_returns_error():
    result = OpenAIAdapter(LLMSettings(enable_api_call=True, openai_api_key="set")).invoke_structured(dict, "{}", _selection())

    assert result.success is False
    assert result.error == "openai_model_not_configured"


def test_openai_adapter_vision_not_implemented():
    result = OpenAIAdapter(LLMSettings(enable_api_call=True, openai_api_key="set", openai_vision_model="vision")).invoke_vision(
        dict,
        "image.png",
        "inspect",
        _selection("api_vision"),
    )

    assert result.success is False
    assert result.error == "openai_vision_not_implemented"
