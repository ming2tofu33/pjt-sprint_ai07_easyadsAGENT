from orchestrator.app.modal import service as modal_service
from orchestrator.app.modal.schemas import ModalPollResult


def test_modal_usage_records_gpu_runtime(monkeypatch):
    calls = []
    row = {
        "id": "job_uuid",
        "workspace_id": "ws_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "user1",
        "model_name": "flux",
        "metadata": {"user_plan": "premium"},
    }
    poll_result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_123",
        usage={"gpu_seconds": "12.5", "gpu_type": "a10g", "duration_ms": 12500},
    )
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: calls.append(kwargs))

    modal_service._record_usage(row, poll_result)

    assert calls[0]["workspace_id"] == "ws_uuid"
    assert calls[0]["runtime_seconds"] == "12.5"
    assert calls[0]["gpu_type"] == "a10g"
    assert calls[0]["modal_call_id"] == "modal_123"
    assert calls[0]["completion_status"] == "succeeded"
    assert calls[0]["created_by"] == "user1"


def test_modal_failed_run_records_runtime_when_available(monkeypatch):
    calls = []
    row = {"id": "job_uuid", "workspace_id": "ws_uuid", "thread_id": "thread_uuid", "requested_by": "user1", "metadata": {"user_plan": "premium"}}
    poll_result = ModalPollResult(status="failed", modal_call_id="modal_123", usage={"gpu_seconds": "3", "gpu_type": "a10g"})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: calls.append(kwargs))

    modal_service._safe_record_modal_usage(row, poll_result)

    assert calls[0]["runtime_seconds"] == "3"
    assert calls[0]["completion_status"] == "failed"


def test_modal_success_records_gpu_runtime_and_t2i_image(monkeypatch):
    runtime_calls = []
    t2i_calls = []
    row = {"id": "job_uuid", "workspace_id": "ws_uuid", "thread_id": "thread_uuid", "requested_by": "user1", "engine": "flux", "metadata": {"user_plan": "premium"}}
    poll_result = ModalPollResult(status="succeeded", modal_call_id="modal_123", usage={"gpu_seconds": "3", "gpu_type": "a10g", "image_count": 1})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: runtime_calls.append(kwargs))
    monkeypatch.setattr(modal_service.usage_service, "record_t2i_usage", lambda **kwargs: t2i_calls.append(kwargs))

    modal_service._safe_record_modal_usage(row, poll_result)
    modal_service._safe_record_modal_t2i_usage(row, poll_result)

    assert runtime_calls[0]["created_by"] == "user1"
    assert t2i_calls[0]["image_count"] == 1
    assert t2i_calls[0]["created_by"] == "user1"


def test_modal_usage_failure_does_not_break_job_completion(monkeypatch):
    row = {"id": "job_uuid", "workspace_id": "ws_uuid"}
    poll_result = ModalPollResult(status="succeeded", modal_call_id="modal_123", usage={"gpu_seconds": "3"})
    monkeypatch.setattr(modal_service.usage_service, "record_modal_gpu_usage", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    assert modal_service._safe_record_modal_usage(row, poll_result) is None
