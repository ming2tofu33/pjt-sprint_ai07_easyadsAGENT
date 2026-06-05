from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.t2i.engines.base import T2IGenerationOutput
from orchestrator.app.t2i.engines.flux_local import FluxPromptTokenBudgetError


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


class FakeFluxEngine:
    engine_name = "flux"

    def generate(self, request):
        path = Path(request.output_dir) / "flux_0.png"
        Image.new("RGB", (128, 128), "#DDEEFF").save(path)
        return T2IGenerationOutput(
            engine="flux",
            image_paths=[path.as_posix()],
            latency_ms=5,
            metadata={"hf_token": "blocked", "model_source": "model_id", "local_path_present": False},
        )


class CapturingFluxEngine(FakeFluxEngine):
    last_request = None

    def generate(self, request):
        CapturingFluxEngine.last_request = request
        return super().generate(request)


class FailingFluxEngine:
    engine_name = "flux"

    def generate(self, request):
        raise FluxPromptTokenBudgetError("budget failed")


def test_flux_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeFluxEngine())
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="flux_local_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "flux")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "flux"
    assert done.result_payload["final_image_path"] == f"data/outputs/{job.job_id}/final_0.png"
    assert done.result_payload["download_url"] is None
    assert done.result_payload["final_image_url"] is None
    assert done.metadata["effective_run_mode"] == "flux_local"
    assert done.metadata["t2i_engine"] == "flux"
    assert Path(done.result_payload["final_image_path"]).exists()
    assert "blocked" not in str(done.model_dump(mode="json"))


def test_flux_request_metadata_is_forwarded_to_engine_with_allowlist(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: CapturingFluxEngine())
    request = GenerationJobCreateRequest(
        user_input="Create a cafe ad",
        run_mode="flux_local_smoke",
        metadata={
            "business_type": "cafe",
            "case_id": "cafe_dessert_001",
            "primary_subject": "strawberry latte",
            "api_key": "sk-blocked",
            "debug": {"safe": "not-forwarded"},
        },
    )
    job = create_generation_job(request)

    execute_generation_job_t2i(job.job_id, request, "flux")

    metadata = CapturingFluxEngine.last_request.metadata
    assert metadata["business_type"] == "cafe"
    assert metadata["case_id"] == "cafe_dessert_001"
    assert metadata["primary_subject"] == "strawberry latte"
    assert "api_key" not in metadata
    assert "debug" not in metadata


def test_flux_prompt_budget_error_preserves_specific_error_code(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FailingFluxEngine())
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="flux_local_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "flux")

    assert failed.status == "failed"
    assert failed.error.error_code == "flux_prompt_token_budget_unresolvable"
    assert failed.error.error_type == "FluxPromptTokenBudgetError"
