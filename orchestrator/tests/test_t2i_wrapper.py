from pathlib import Path

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.mock import MockT2IEngine
from orchestrator.app.t2i.router import get_t2i_engine, get_t2i_health
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


def test_t2i_settings_reads_defaults():
    settings = get_t2i_settings()

    assert settings.default_engine == "mock"
    assert settings.gpt_image_model == "gpt-image-2"
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


def test_t2i_health_reports_mock_and_unimplemented_engines():
    health = get_t2i_health()

    assert health["mock"]["available"] is True
    assert health["mock"]["loaded"] is True
    assert health["sd35_large"]["available"] is False
    assert health["flux"]["available"] is False
    assert "reason" in health["gpt_image_2"]


def test_router_returns_default_mock_engine():
    engine = get_t2i_engine()

    assert engine.name == "mock"