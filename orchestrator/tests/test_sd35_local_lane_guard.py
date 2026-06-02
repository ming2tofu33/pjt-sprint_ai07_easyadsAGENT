from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests


def test_sd35_default_env_does_not_load_model(monkeypatch):
    reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_ENABLE_SD35_LOCAL", raising=False)
    monkeypatch.setenv("HF_TOKEN", "hf-should-not-leak")
    request = GenerationJobCreateRequest(user_input="Create a restaurant ad", run_mode="sd35_local_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "sd35_large")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "t2i_engine_not_enabled"
    assert "hf-should-not-leak" not in str(failed.model_dump(mode="json"))

