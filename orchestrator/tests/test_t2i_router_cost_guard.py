import pytest

from orchestrator.app.t2i.gpt_image2 import GPTImage1Engine, GPTImage2Engine
from orchestrator.app.t2i.router import get_t2i_engine

GPT_IMAGE_ENGINES = [
    ("gpt_image_1", "EASYADS_ENABLE_GPT_IMAGE_1", GPTImage1Engine),
    ("gpt_image_2", "EASYADS_ENABLE_GPT_IMAGE_2", GPTImage2Engine),
]


@pytest.mark.parametrize(("engine_name", "enable_flag", "engine_cls"), GPT_IMAGE_ENGINES)
def test_router_requires_strong_guard_when_legacy_api_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
    engine_name: str,
    enable_flag: str,
    engine_cls: type[GPTImage1Engine | GPTImage2Engine],
) -> None:
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "true")
    monkeypatch.setenv("T2I_ENABLE_API_COST_GUARD", "true")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv(enable_flag, "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    engine = get_t2i_engine(engine_name)

    assert isinstance(engine, engine_cls)
    assert engine.allow_api_call is False


@pytest.mark.parametrize(("engine_name", "enable_flag", "engine_cls"), GPT_IMAGE_ENGINES)
def test_router_requires_legacy_api_flag_when_strong_guard_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
    engine_name: str,
    enable_flag: str,
    engine_cls: type[GPTImage1Engine | GPTImage2Engine],
) -> None:
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "false")
    monkeypatch.setenv("T2I_ENABLE_API_COST_GUARD", "true")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv(enable_flag, "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    engine = get_t2i_engine(engine_name)

    assert isinstance(engine, engine_cls)
    assert engine.allow_api_call is False


@pytest.mark.parametrize(("engine_name", "enable_flag", "engine_cls"), GPT_IMAGE_ENGINES)
def test_router_fails_closed_when_cost_guard_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    engine_name: str,
    enable_flag: str,
    engine_cls: type[GPTImage1Engine | GPTImage2Engine],
) -> None:
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "true")
    monkeypatch.setenv("T2I_ENABLE_API_COST_GUARD", "false")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv(enable_flag, "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    engine = get_t2i_engine(engine_name)

    assert isinstance(engine, engine_cls)
    assert engine.allow_api_call is False


@pytest.mark.parametrize(("engine_name", "enable_flag", "engine_cls"), GPT_IMAGE_ENGINES)
def test_router_allows_gpt_image_api_only_when_all_guards_pass(
    monkeypatch: pytest.MonkeyPatch,
    engine_name: str,
    enable_flag: str,
    engine_cls: type[GPTImage1Engine | GPTImage2Engine],
) -> None:
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "true")
    monkeypatch.setenv("T2I_ENABLE_API_COST_GUARD", "true")
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv(enable_flag, "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    engine = get_t2i_engine(engine_name)

    assert isinstance(engine, engine_cls)
    assert engine.allow_api_call is True
