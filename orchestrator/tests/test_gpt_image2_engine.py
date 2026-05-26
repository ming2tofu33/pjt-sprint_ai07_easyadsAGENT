"""Tests for the cost-safe GPT-image-2 T2I engine."""

from orchestrator.app.t2i.gpt_image2 import GPTImage2Engine
from orchestrator.app.t2i.schemas import T2IRequest


def test_gpt_image2_health_reports_missing_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    engine = GPTImage2Engine()

    health = engine.health()

    assert health["available"] is False
    assert health["loaded"] is False
    assert health["reason"] == "OPENAI_API_KEY missing"


def test_gpt_image2_generate_returns_error_when_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    engine = GPTImage2Engine(allow_api_call=True)
    request = T2IRequest(
        prompt="Korean BBQ restaurant poster background, no text",
        output_dir=str(tmp_path),
        metadata={"job_id": "missing-key-test"},
    )

    result = engine.generate(request)

    assert result.engine == "gpt_image_2"
    assert result.image_paths == []
    assert result.error == "OPENAI_API_KEY missing"
    assert result.metadata["api_call"] is False


def test_gpt_image2_generate_blocks_api_call_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    engine = GPTImage2Engine(allow_api_call=False)
    request = T2IRequest(
        prompt="Korean BBQ restaurant poster background, no text",
        output_dir=str(tmp_path),
        metadata={"job_id": "blocked-api-test"},
    )

    result = engine.generate(request)

    assert result.engine == "gpt_image_2"
    assert result.image_paths == []
    assert result.error == "API call disabled; pass allow_api_call=True or --include-api"
    assert result.metadata["api_call"] is False
