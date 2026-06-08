from __future__ import annotations

import sys
import types
from pathlib import Path

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage1ActualEngine, GPTImage2ActualEngine


_ONE_BY_ONE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_gpt_image_1_default_env_does_not_call_api(monkeypatch):
    reset_generation_job_store_for_tests()
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")

    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="gpt_image_1_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "gpt_image_1")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "t2i_engine_not_enabled"
    assert "sk-should-not-leak" not in str(failed.model_dump(mode="json"))


def test_gpt_image2_actual_engine_does_not_send_response_format(monkeypatch, tmp_path: Path):
    captured_kwargs = {}

    class FakeImages:
        def generate(self, **kwargs):
            captured_kwargs.update(kwargs)
            return types.SimpleNamespace(
                data=[
                    types.SimpleNamespace(
                        b64_json=_ONE_BY_ONE_PNG_B64,
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.images = FakeImages()

    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    request = T2IGenerationInput(
        job_id="job_unit_test_gpt_image_2",
        prompt="premium cafe advertising background with clean text space",
        negative_prompt="text, letters, logo, watermark",
        width=1024,
        height=1024,
        num_images=1,
        output_dir=tmp_path.as_posix(),
        metadata={"case_id": "unit_test"},
    )
    output = GPTImage2ActualEngine().generate(request)

    assert captured_kwargs["model"]
    assert captured_kwargs["prompt"] == request.prompt
    assert captured_kwargs["size"] == "1024x1024"
    assert captured_kwargs["n"] == 1
    assert "response_format" not in captured_kwargs

    assert output.engine == "gpt_image_2"
    assert output.image_paths
    assert Path(output.image_paths[0]).exists()
    assert output.metadata["api_call"] is True
    assert "sk-test-secret" not in str(output.metadata)


def test_gpt_image1_actual_engine_uses_gpt_image_1(monkeypatch, tmp_path: Path):
    captured_kwargs = {}

    class FakeImages:
        def generate(self, **kwargs):
            captured_kwargs.update(kwargs)
            return types.SimpleNamespace(data=[types.SimpleNamespace(b64_json=_ONE_BY_ONE_PNG_B64)])

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.images = FakeImages()

    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "true")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    request = T2IGenerationInput(
        job_id="job_unit_test_gpt_image_1",
        prompt="premium cafe advertising background with clean text space",
        width=1024,
        height=1024,
        output_dir=tmp_path.as_posix(),
    )
    output = GPTImage1ActualEngine().generate(request)

    assert captured_kwargs["model"] == "gpt-image-1"
    assert output.engine == "gpt_image_1"
    assert output.image_paths == [str(tmp_path / "gpt_image_1_0.png")]
