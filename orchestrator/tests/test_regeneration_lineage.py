from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx():
    yield object()


def test_regeneration_creates_job_with_internal_lineage_and_public_response(monkeypatch):
    captured = {}

    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_db_by_id", lambda *args, **kwargs: {"id": "job_uuid", "public_job_id": "job_old", "regeneration_depth": 0, "run_mode": "queued_only", "metadata": {"public_thread_id": "thread_1"}})

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {"id": "job_new_uuid", "public_job_id": "job_new", "status": "queued", "regeneration_depth": kwargs["regeneration_depth"], "metadata": kwargs["metadata"]}

    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.create_generation_job_row", fake_create)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.thread_repo.set_chat_thread_active_job", lambda *args, **kwargs: {})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.event_repo.record_generation_job_event", lambda **kwargs: {})

    status_code, body = regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction="short", idempotency_key="idem-123456")

    assert status_code == 202
    assert captured["parent_job_id"] == "job_uuid"
    assert captured["previous_output_id"] == "out_uuid"
    assert captured["regeneration_depth"] == 1
    assert body["parentJobId"] == "job_old"
    assert body["previousOutputId"] == "output_old"
    assert "job_uuid" not in str(body)
