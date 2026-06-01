from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests


def test_gpt_image_2_default_env_does_not_call_api(monkeypatch):
    reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_ENABLE_EXTERNAL_T2I", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_GPT_IMAGE_2", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="gpt_image_2_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "gpt_image_2")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "t2i_engine_not_enabled"
    assert "sk-should-not-leak" not in str(failed.model_dump(mode="json"))

