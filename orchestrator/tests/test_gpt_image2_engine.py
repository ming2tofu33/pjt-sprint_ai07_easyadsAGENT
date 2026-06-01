"""Tests for the cost-safe GPT-image-2 T2I engine."""

import base64
from types import SimpleNamespace

import openai

from orchestrator.app.t2i.gpt_image2 import GPTImage2Engine, _resolve_model, _resolve_size
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


def test_gpt_image2_uses_edit_when_input_image_is_present(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setenv("T2I_GPT_IMAGE_MODEL", "gpt-image-1")
    source = tmp_path / "source.png"
    source.write_bytes(b"fake image")
    called = {}

    class FakeImages:
        def edit(self, **kwargs):
            called["operation"] = "edit"
            called["kwargs"] = kwargs
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"fake output").decode("ascii"))])

        def generate(self, **kwargs):
            called["operation"] = "generate"
            called["kwargs"] = kwargs
            return SimpleNamespace(data=[])

    class FakeOpenAI:
        def __init__(self, api_key):
            called["api_key"] = api_key
            self.images = FakeImages()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    engine = GPTImage2Engine(allow_api_call=True)
    request = T2IRequest(
        prompt="Use the uploaded drink photo as the product reference",
        input_image_paths=[str(source)],
        output_dir=str(tmp_path / "out"),
        metadata={"job_id": "image-edit-test"},
    )

    result = engine.generate(request)

    assert called["operation"] == "edit"
    assert called["kwargs"]["model"] == "gpt-image-1"
    assert called["kwargs"]["input_fidelity"] == "high"
    assert "response_format" not in called["kwargs"]
    assert called["kwargs"]["image"][0].name == str(source)
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "out" / "gpt_image_2_0.png")]
    assert result.metadata["api_operation"] == "edit"
    assert result.metadata["input_image_paths"] == [str(source)]


def test_gpt_image2_resolves_supported_image_api_values():
    assert _resolve_model("gpt-image-2") == "gpt-image-2"
    assert _resolve_model("gpt-image-1") == "gpt-image-1"
    assert _resolve_model("unknown-image-model") == "gpt-image-1"
    assert _resolve_size(1080, 1080) == "1024x1024"
    assert _resolve_size(1200, 628) == "1536x1024"
    assert _resolve_size(1080, 1920) == "1024x1536"
