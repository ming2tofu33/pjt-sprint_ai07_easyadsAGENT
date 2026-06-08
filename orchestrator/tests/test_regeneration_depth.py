from contextlib import contextmanager

import pytest

from orchestrator.app.validation_feedback.errors import RegenerationDepthExceeded
from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx():
    yield object()


def test_regeneration_depth_limit_blocks_new_job(monkeypatch):
    monkeypatch.setenv("EASYADS_MAX_REGENERATION_DEPTH", "1")
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_db_by_id", lambda *args, **kwargs: {"id": "job_uuid", "regeneration_depth": 1})

    with pytest.raises(RegenerationDepthExceeded):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")
