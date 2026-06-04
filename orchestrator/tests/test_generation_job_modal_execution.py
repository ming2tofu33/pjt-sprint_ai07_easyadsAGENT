from datetime import datetime, timezone

from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs import service
from orchestrator.app.modal.schemas import ModalSubmitResult


def _job(status="queued") -> GenerationJobResponse:
    now = datetime.now(timezone.utc).isoformat()
    return GenerationJobResponse(
        job_id="job_modal",
        thread_id="thread_modal",
        status=status,
        progress=GenerationProgress(progress_percent=0, current_stage=status),
        selected_reference_template_id=None,
        output_path=None,
        result_payload=None,
        error=None,
        created_at=now,
        updated_at=now,
        metadata={"requested_run_mode": "flux_local", "effective_run_mode": "flux_local"},
    )


def _row():
    return {
        "id": "job_uuid",
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "flux_local",
        "engine": "flux",
        "prompt_preview": "Create an ad",
        "metadata": {"public_thread_id": "thread_modal"},
    }


def test_modal_router_policy_only_applies_to_modal_backend(monkeypatch):
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux_local")

    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    assert service.should_route_generation_job_to_modal(request) is False

    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    assert service.should_route_generation_job_to_modal(request) is True

    gpt_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="gpt_image_2_actual")
    assert service.should_route_generation_job_to_modal(gpt_request) is False


def test_modal_disabled_marks_job_failed_without_local_model_execution(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.delenv("EASYADS_ENABLE_MODAL_EXECUTION", raising=False)
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    captured = {}

    def fake_failed(job_id, error, metadata=None):
        captured["job_id"] = job_id
        captured["error"] = error
        return _job(status="failed").model_copy(update={"error": ErrorResponse(**error)})

    monkeypatch.setattr(service, "mark_generation_job_failed", fake_failed)

    result = service.maybe_submit_generation_job_to_modal(
        _job(),
        GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux_local"),
    )

    assert result.status == "failed"
    assert captured["error"]["error_code"] == "modal_execution_not_enabled"


def test_modal_enabled_submits_and_returns_latest_job(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: _row())
    captured = {}

    def fake_submit(job_row, modal_request):
        captured["job_row"] = job_row
        captured["modal_request"] = modal_request
        return ModalSubmitResult(submitted=True, modal_call_id="modal_call_1", status="submitted")

    monkeypatch.setattr(service, "submit_generation_job_to_modal", fake_submit)
    monkeypatch.setattr(service, "get_generation_job", lambda job_id: _job(status="running"))

    result = service.maybe_submit_generation_job_to_modal(
        _job(),
        GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux_local"),
    )

    assert result.status == "running"
    assert captured["modal_request"].engine == "flux"
    assert captured["modal_request"].job_id == "job_modal"
