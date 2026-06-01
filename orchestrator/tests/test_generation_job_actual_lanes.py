from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.t2i.engines.base import T2IGenerationOutput


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


class FakeEngine:
    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name

    def generate(self, request):
        path = Path(request.output_dir) / f"{self.engine_name}_generated.png"
        Image.new("RGB", (128, 128), "#ABCDEF").save(path)
        return T2IGenerationOutput(engine=self.engine_name, image_paths=[path.as_posix()], latency_ms=3, metadata={"api_key": "blocked"})


def test_gpt_image_2_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeEngine(name))
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="gpt_image_2_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "gpt_image_2")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "gpt_image_2"
    assert done.output_path == f"data/outputs/{job.job_id}/final_0.png"
    assert Path(done.output_path).exists()
    assert "blocked" not in str(done.model_dump(mode="json"))


def test_sd35_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeEngine(name))
    request = GenerationJobCreateRequest(user_input="Create a bbq ad", run_mode="sd35_local_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "sd35_large")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "sd35_large"
    assert Path(done.result_payload["metadata_path"]).exists()

