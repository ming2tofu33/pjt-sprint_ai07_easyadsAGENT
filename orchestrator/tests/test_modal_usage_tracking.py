from orchestrator.app.modal import service as modal_service
from orchestrator.app.modal.schemas import ModalPollResult


def test_modal_usage_records_gpu_runtime(monkeypatch):
    calls = []
    row = {
        "id": "job_uuid",
        "workspace_id": "ws_uuid",
        "thread_id": "thread_uuid",
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
