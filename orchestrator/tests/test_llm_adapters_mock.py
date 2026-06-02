from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.openai import OpenAIAdapter
from orchestrator.app.llm.adapters.registry import ProviderNotImplementedError, get_llm_adapter, get_llm_adapter_safe
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection() -> ModelSelection:
    return choose_model("validator", "free")


def test_mock_adapter_invoke_text():
    result = MockLLMAdapter().invoke_text(
        "hello",
        _selection(),
        metadata={
            "prompt": "secret",
            "hf_token": "secret-token",
            "raw_image_bytes": b"secret-bytes",
            "chain_of_thought": "private reasoning",
            "token_usage": {"prompt_tokens": 1},
        },
    )

    assert result.success is True
    assert result.output == "mock text response"
    assert result.cost_estimate == 0.0
    assert result.metadata["mock"] is True
    assert result.metadata["token_usage"]["prompt_tokens"] == 1
    assert "secret" not in str(result.metadata)
    assert "chain_of_thought" not in result.metadata


def test_mock_adapter_invoke_structured():
    result = MockLLMAdapter().invoke_structured(ModelSelection, "select", _selection())

    assert result.success is True
    assert result.model_selection.node_name == "validator"
    assert result.output["mock"] is True


def test_mock_adapter_invoke_vision():
    result = MockLLMAdapter().invoke_vision(dict, "image.png", "inspect", _selection())

    assert result.success is True
    assert result.output["image_path"] == "image.png"
    assert result.metadata["vision"] is True


def test_adapter_registry_returns_safe_mock_fallback():
    assert isinstance(get_llm_adapter("mock"), MockLLMAdapter)
    assert isinstance(get_llm_adapter("openai"), OpenAIAdapter)
    try:
        get_llm_adapter("local_gemma")
    except ProviderNotImplementedError:
        pass
    else:
        raise AssertionError("local_gemma should be explicit not implemented in strict mode")
    assert isinstance(get_llm_adapter("local_gemma", allow_mock_fallback=True), MockLLMAdapter)
    assert isinstance(get_llm_adapter_safe("vision_api", LLMSettings(provider_strict_mode=True)), MockLLMAdapter)
