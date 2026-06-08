from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.service import _request_fingerprint
from orchestrator.app.validation_feedback.errors import RegenerationIdempotencyConflict
import pytest


@contextmanager
def _fake_tx():
    yield object()


def test_regeneration_idempotency_replays_existing_job(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"suggested_actions": [{"code": "remove_fake_text"}]})
    fingerprint = _request_fingerprint(public_output_id="output_old", actions=["remove_fake_text"], scope="image", user_instruction=None)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: {"public_job_id": "job_existing", "status": "queued", "regeneration_depth": 1, "previous_output_id": "out_uuid", "metadata": {"public_thread_id": "thread_1", "regeneration_fingerprint": fingerprint}})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.event_repo.record_generation_job_event", lambda **kwargs: {})

    status_code, body = regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[], scope=None, user_instruction=None, idempotency_key="idem-123456")

    assert status_code == 200
    assert body["jobId"] == "job_existing"
    assert body["idempotentReplay"] is True


def test_regeneration_idempotency_conflicts_for_different_output(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_b", "public_output_id": "output_b", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: {"public_job_id": "job_existing", "status": "queued", "regeneration_depth": 1, "previous_output_id": "out_a", "metadata": {"regeneration_fingerprint": "old"}})

    with pytest.raises(RegenerationIdempotencyConflict):
        regenerate_output(public_output_id="output_b", workspace_id="ws", suggested_actions=[ ], scope=None, user_instruction=None, idempotency_key="idem-123456")
