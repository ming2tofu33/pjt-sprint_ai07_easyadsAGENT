"""Consolidated regeneration tests.

Merged from:
- orchestrator/tests/test_regeneration_api.py
- orchestrator/tests/test_regeneration_depth.py
- orchestrator/tests/test_regeneration_idempotency.py
- orchestrator/tests/test_regeneration_invalid_action.py
- orchestrator/tests/test_regeneration_lineage.py
- orchestrator/tests/test_regeneration_policy.py
- orchestrator/tests/test_regeneration_thread_state.py
"""



# ===== from test_regeneration_api.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_regeneration_api_returns_accepted_job(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_new",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
            },
        ),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "scope": "image", "idempotencyKey": "idem-123456"},
    )

    assert response.status_code == 202
    assert response.json()["regeneration"]["jobId"] == "job_new"


def test_regeneration_api_dispatches_created_graph_job(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_new",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
                "_dispatch": {
                    "jobId": "job_new",
                    "runMode": "graph_job",
                    "request": {"userInput": "regenerate", "threadId": "thread_1", "runMode": "graph_job", "metadata": {"regeneration_patch": {"scope": "image", "patches": {}}}},
                },
            },
        ),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.execute_generation_job_graph",
        lambda job_id, request: calls.append((job_id, request.run_mode, request.metadata)),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "idempotencyKey": "idem-123456"},
    )

    assert response.status_code == 202
    assert calls == [("job_new", "graph_job", {"regeneration_patch": {"scope": "image", "patches": {}}})]
    assert "_dispatch" not in str(response.json())


def test_regeneration_api_dispatches_gpt_image_1_job(monkeypatch):
    calls = []
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.regenerate_output",
        lambda **kwargs: (
            202,
            {
                "jobId": "job_gpt1",
                "threadId": "thread_1",
                "parentJobId": "job_old",
                "previousOutputId": "output_old",
                "depth": 1,
                "status": "queued",
                "appliedActions": ["remove_fake_text"],
                "idempotentReplay": False,
                "_dispatch": {
                    "jobId": "job_gpt1",
                    "runMode": "gpt_image_1_actual",
                    "request": {
                        "userInput": "regenerate",
                        "threadId": "thread_1",
                        "runMode": "gpt_image_1_actual",
                        "metadata": {"regeneration_patch": {"scope": "image", "patches": {}}},
                    },
                },
            },
        ),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.execute_generation_job_t2i",
        lambda job_id, request, engine_name: calls.append((job_id, request.run_mode, engine_name, request.metadata)),
    )

    response = TestClient(create_app()).post(
        "/api/v1/generation-outputs/output_old/regenerate?workspace_id=ws",
        json={"suggestedActions": ["remove_fake_text"], "idempotencyKey": "idem-gpt1"},
    )

    assert response.status_code == 202
    assert calls == [("job_gpt1", "gpt_image_1_actual", "gpt_image_1", {"regeneration_patch": {"scope": "image", "patches": {}}})]
    assert "_dispatch" not in str(response.json())


# ===== from test_regeneration_depth.py =====
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
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_db_by_id", lambda *args, **kwargs: {"id": "job_uuid", "regeneration_depth": 1})

    with pytest.raises(RegenerationDepthExceeded):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")


# ===== from test_regeneration_idempotency.py =====
from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.service import _request_fingerprint
from orchestrator.app.validation_feedback.errors import RegenerationIdempotencyConflict
import pytest


@contextmanager
def _fake_tx__test_regeneration_idempotency():
    yield object()


def test_regeneration_idempotency_replays_existing_job(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_idempotency())
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
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_idempotency())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_b", "public_output_id": "output_b", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: {"public_job_id": "job_existing", "status": "queued", "regeneration_depth": 1, "previous_output_id": "out_a", "metadata": {"regeneration_fingerprint": "old"}})

    with pytest.raises(RegenerationIdempotencyConflict):
        regenerate_output(public_output_id="output_b", workspace_id="ws", suggested_actions=[ ], scope=None, user_instruction=None, idempotency_key="idem-123456")


# ===== from test_regeneration_invalid_action.py =====
from contextlib import contextmanager

import pytest

from orchestrator.app.validation_feedback.errors import InvalidRegenerationAction, InvalidRegenerationScope, RegenerationNotRecommended
from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx__test_regeneration_invalid_action():
    yield object()


def test_regeneration_rejects_client_action_not_in_server_report(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_invalid_action())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "increase_copy_safe_area"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(InvalidRegenerationAction):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_manual_review_only_action(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_invalid_action())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "manual_review"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(RegenerationNotRecommended):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.MANUAL_REVIEW], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_manual_review_mixed_with_retry_action(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_invalid_action())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "manual_review"}, {"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(RegenerationNotRecommended):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.MANUAL_REVIEW, SuggestedActionCode.REMOVE_FAKE_TEXT], scope=None, user_instruction=None, idempotency_key="idem-123456")


def test_regeneration_rejects_client_scope_conflict(monkeypatch):
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_invalid_action())
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id", lambda **kwargs: {"id": "out_uuid", "public_output_id": "output_old", "workspace_id": "ws", "thread_id": "thread_uuid", "job_id": "job_uuid", "public_job_id": "job_old", "public_thread_id": "thread_1", "asset_id": "asset_uuid", "output_type": "final_image"})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.report_repo.get_latest_validation_report_for_output", lambda **kwargs: {"public_validation_report_id": "validation_1", "suggested_actions": [{"code": "remove_fake_text"}]})
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.job_repo.get_generation_job_by_regeneration_idempotency_key", lambda **kwargs: None)

    with pytest.raises(InvalidRegenerationScope):
        regenerate_output(public_output_id="output_old", workspace_id="ws", suggested_actions=[SuggestedActionCode.REMOVE_FAKE_TEXT], scope="layout", user_instruction=None, idempotency_key="idem-123456")


# ===== from test_regeneration_lineage.py =====
from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx__test_regeneration_lineage():
    yield object()


def test_regeneration_creates_job_with_internal_lineage_and_public_response(monkeypatch):
    captured = {}

    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_lineage())
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


# ===== from test_regeneration_policy.py =====
from orchestrator.app.validation_feedback.regeneration_policy import build_regeneration_patch


def test_regeneration_policy_builds_structured_patch_without_raw_state():
    patch = build_regeneration_patch(["increase_copy_safe_area", "remove_fake_text"], user_instruction="short note")

    assert patch["scope"] == "full"
    assert patch["actions"] == ["remove_fake_text", "increase_copy_safe_area"]
    assert patch["patches"]["remove_fake_text"]["changeSeed"] is True
    assert "local_path" not in str(patch)


# ===== from test_regeneration_thread_state.py =====
from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import regenerate_output
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


@contextmanager
def _fake_tx__test_regeneration_thread_state():
    yield object()


def test_regeneration_updates_active_job_but_not_final_output(monkeypatch):
    thread_calls = []
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx__test_regeneration_thread_state())
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
