from datetime import datetime, timezone

from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs import service
from orchestrator.app.modal.errors import ModalJobPollError
from orchestrator.app.modal.schemas import ModalPollResult
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

    real_flux_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux_schnell_real")
    assert service.should_route_generation_job_to_modal(real_flux_request) is True

    real_sd35_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="sd35_large_real")
    assert service.should_route_generation_job_to_modal(real_sd35_request) is True


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


def test_modal_backend_records_model_provider_as_modal(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")

    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux_local")

    assert service._model_provider_for_request(request) == "modal"
    assert service._model_name_for_run_mode(request.run_mode) == "flux"

    sd35_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="sd35_large_real")
    assert service._model_provider_for_request(sd35_request) == "modal"
    assert service._model_name_for_run_mode(sd35_request.run_mode) == "sd35_large"


def test_modal_poll_adapter_unavailable_does_not_fail_job(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_POLL_ON_GET", "true")
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    events = []
    row = {**_row(), "modal_call_id": "modal_call_1", "status": "running"}

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: row)

    def raise_poll(job_id):
        raise ModalJobPollError("poll adapter unavailable")

    monkeypatch.setattr(service, "poll_and_process_modal_generation_job", raise_poll)
    monkeypatch.setattr(
        service.generation_job_event_repo,
        "record_generation_job_event",
        lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"},
    )

    result = service.maybe_poll_generation_job_from_modal(_job(status="running"))

    assert result.status == "running"
    assert events[0]["event_type"] == "modal_poll_unavailable"
    assert events[0]["payload"]["error_code"] == "modal_poll_adapter_unavailable"


def test_graph_modal_pending_polls_through_graph_completion_path(monkeypatch):
    captured = {}

    def fake_graph_poll(job_id):
        captured["job_id"] = job_id
        return _job(status="done")

    monkeypatch.setattr(service, "_use_postgres_backend", lambda: False)
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.execution.poll_and_process_graph_modal_generation_job",
        fake_graph_poll,
    )

    job = _job(status="running").model_copy(
        update={
            "metadata": {
                "requested_run_mode": "graph_job",
                "effective_run_mode": "graph_job",
                "graph_modal_pending": True,
                "modal_call_id": "modal_call_graph",
            }
        }
    )

    result = service.maybe_poll_generation_job_from_modal(job)

    assert result.status == "done"
    assert captured["job_id"] == "job_modal"


def test_modal_success_uses_storage_backed_result_payload_contract(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}
    poll_result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_call_1",
        image_b64="aW1hZ2U=",
        result_payload={"schema_version": "result_artifact_v1"},
    )

    from orchestrator.app.modal import service as modal_service

    monkeypatch.setattr(modal_service.job_repo, "get_generation_job_row", lambda job_id: _row() | {"modal_call_id": "modal_call_1"})
    monkeypatch.setattr(modal_service, "poll_modal_t2i_result", lambda modal_call_id, client=None: poll_result)
    monkeypatch.setattr(modal_service, "_record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(modal_service, "_record_usage", lambda *args, **kwargs: None)

    def fake_mark_done(job_id, result_payload, output_path=None, metadata=None):
        captured["job_id"] = job_id
        captured["result_payload"] = result_payload
        captured["output_path"] = output_path
        return _job(status="done").model_copy(update={"result_payload": result_payload, "output_path": output_path})

    monkeypatch.setattr(service_module := __import__("orchestrator.app.generation_jobs.service", fromlist=["service"]), "mark_generation_job_done", fake_mark_done)
    monkeypatch.setattr(service_module, "get_generation_job", lambda job_id: _job(status="running"))
    monkeypatch.setattr(service_module, "mark_generation_job_running", lambda job_id, stage="running": _job(status="running"))
    monkeypatch.setattr(service_module, "mark_generation_job_failed", lambda job_id, error, metadata=None: _job(status="failed"))

    result = modal_service.poll_and_process_modal_generation_job(job_id="job_modal")

    assert result.status == "done"
    assert captured["job_id"] == "job_modal"
    assert captured["result_payload"]["schema_version"] == "result_artifact_v1"
    assert captured["result_payload"]["render_mode"] == "modal"
    assert captured["result_payload"]["final_image_path"] == "data/outputs/job_modal/final_0.png"
    assert "image_b64" not in str(captured["result_payload"])
    assert "image_bytes" not in str(captured["result_payload"])
