from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx():
    yield object()


def test_regeneration_updates_active_job_but_not_final_output(monkeypatch):
    thread_calls = []
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_db_by_id", lambda *args, **kwargs: {"id": "job_uuid", "regeneration_depth": 0})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.create_generation_job_row", lambda **kwargs: {"id": "job_new_uuid", "public_job_id": "job_new", "status": "queued", "regeneration_depth": 1, "metadata": {}})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.thread_repo.set_chat_thread_active_job", lambda *args, **kwargs: thread_calls.append(kwargs) or {})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.event_repo.record_generation_job_event", lambda **kwargs: {})

    regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")

    assert thread_calls[0]["active_job_id"] == "job_new_uuid"
    assert "final_output_id" not in thread_calls[0]
