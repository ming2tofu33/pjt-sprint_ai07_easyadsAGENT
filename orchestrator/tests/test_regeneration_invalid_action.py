from contextlib import contextmanager

import pytest

from orchestrator.app.validation_feedback.errors import InvalidRegenerationAction, InvalidRegenerationScope, RegenerationNotRecommended
from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx():
    yield object()


def test_regeneration_rejects_client_action_not_in_server_report(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "increase_copy_safe_area"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(InvalidRegenerationAction):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_manual_review_only_action(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "manual_review"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(RegenerationNotRecommended):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.MANUAL_REVIEW], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_manual_review_mixed_with_retry_action(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "manual_review"}, {"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(RegenerationNotRecommended):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.MANUAL_REVIEW, SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_client_scope_conflict(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(InvalidRegenerationScope):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope="layout", user_instruction=None, idempotency_key="idem-123456")
