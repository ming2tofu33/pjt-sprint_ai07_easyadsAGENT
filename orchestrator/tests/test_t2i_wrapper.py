from pathlib import Path

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.mock import MockT2IEngine
from orchestrator.app.t2i.router import get_t2i_engine, get_t2i_health
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


def test_t2i_settings_reads_defaults(monkeypatch):
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    monkeypatch.setenv("T2I_ALLOW_API_CALLS", "false")
    monkeypatch.setenv("T2I_GPT_IMAGE_MODEL", "gpt-image-1")

    settings = get_t2i_settings()

    assert settings.default_engine == "mock"
    assert settings.allow_api_calls is False
    assert settings.gpt_image_model == "gpt-image-1"
    assert settings.sd35_model_id == "stabilityai/stable-diffusion-3.5-large"
    assert settings.flux_model_id == "black-forest-labs/FLUX.1-schnell"


def test_mock_engine_generates_placeholder(tmp_path: Path):
    engine = MockT2IEngine()
    request = T2IRequest(
        prompt="Korean BBQ restaurant campaign poster background",
        negative_prompt="text, watermark, logo",
        width=512,
        height=512,
        output_dir=str(tmp_path),
        metadata={"case": "unit"},
    )

    result = engine.generate(request)

    assert isinstance(result, T2IResult)
    assert result.engine == "mock"
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "mock_0.png")]
    assert Path(result.image_paths[0]).exists()
    assert result.metadata["case"] == "unit"


def test_t2i_health_reports_mock_and_graph_actual_engine_status(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "false")

    health = get_t2i_health()

    assert health["mock"]["available"] is True
    assert health["mock"]["loaded"] is True
    assert health["sd35_large"]["available"] is False
    assert health["flux"]["available"] is False
    assert "reason" in health["gpt_image_1"]
    assert "reason" in health["gpt_image_2"]


def test_router_returns_graph_actual_engine_adapters(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")

    assert get_t2i_engine("flux").name == "flux"
    assert get_t2i_engine("sd35_large").name == "sd35_large"


def test_router_returns_default_mock_engine(monkeypatch):
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")

    engine = get_t2i_engine()

    assert engine.name == "mock"
