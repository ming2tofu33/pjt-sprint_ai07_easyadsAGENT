"""Consolidated validation feedback tests.

Merged from:
- orchestrator/tests/test_validation_feedback_action_mapper.py
- orchestrator/tests/test_validation_feedback_api.py
- orchestrator/tests/test_validation_feedback_failure_mapper.py
- orchestrator/tests/test_validation_feedback_repository.py
- orchestrator/tests/test_validation_feedback_security.py
- orchestrator/tests/test_validation_feedback_service.py
"""



# ===== from test_validation_feedback_action_mapper.py =====
from orchestrator.app.validation_feedback.action_mapper import build_suggested_actions, derive_scope
from orchestrator.app.validation_feedback.schemas import ValidationFailureType


def test_action_mapper_dedupes_and_sorts_by_priority():
    actions = build_suggested_actions(
        [
            ValidationFailureType.UNEXPECTED_TEXT,
            ValidationFailureType.FAKE_TEXT,
            ValidationFailureType.COPY_SAFE_AREA,
        ]
    )

    assert [item.code.value for item in actions] == ["remove_fake_text", "increase_copy_safe_area"]
    assert actions[0].priority == 90


def test_derive_scope_uses_full_for_mixed_actions():
    assert derive_scope(["remove_fake_text"]) == "image"
    assert derive_scope(["adjust_copy_layout"]) == "layout"
    assert derive_scope(["remove_fake_text", "adjust_copy_layout"]) == "full"


# ===== from test_validation_feedback_api.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_validation_detail_api_returns_public_contract(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.validation_feedback.resolve_workspace_scope", lambda workspace_id, user_id=None: "ws")
    monkeypatch.setattr(
        "orchestrator.app.api.routers.validation_feedback.get_latest_validation_for_output",
        lambda **kwargs: {
            "reportId": "validation_1",
            "outputId": "output_1",
            "jobId": "job_1",
            "status": "fail",
            "decision": "retry_image",
            "failureTypes": ["fake_text"],
            "suggestedActions": [{"code": "remove_fake_text", "scope": "image", "priority": 90, "reason": "remove text", "parameters": {}}],
            "retryRecommended": True,
            "requiresManualReview": False,
            "schemaVersion": "validation_feedback_v1",
            "createdAt": "2026-06-08T00:00:00Z",
        },
    )

    response = TestClient(create_app()).get("/api/v1/generation-outputs/output_1/validation?workspace_id=ws")

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["reportId"] == "validation_1"
    assert "object_key" not in str(body)


# ===== from test_validation_feedback_failure_mapper.py =====
from orchestrator.app.validation_feedback.failure_mapper import extract_failure_types


def test_failure_mapper_extracts_deterministic_unique_failures():
    failures = extract_failure_types(
        {
            "ocr": {"fakeText": True, "watermark": True, "unexpectedTextCount": 2},
            "safeArea": {"passed": False},
            "readability": {"passed": False, "clipping": True},
            "vlm": {"businessFitScore": 0.5},
        }
    )

    assert [item.value for item in failures] == [
        "watermark",
        "fake_text",
        "unexpected_text",
        "copy_clipping",
        "copy_safe_area",
        "copy_unreadable",
        "business_fit",
    ]


def test_provider_unavailable_adds_manual_review_failure():
    failures = extract_failure_types({"ocr": {"providerStatus": "unavailable"}})

    assert [item.value for item in failures] == ["provider_unavailable", "manual_review_required"]


# ===== from test_validation_feedback_repository.py =====
from pathlib import Path


def test_validation_feedback_migration_contains_append_only_schema():
    sql = Path("supabase/migrations/20260608_validation_feedback_regeneration_v1.sql").read_text(encoding="utf-8")

    assert "create table if not exists validation_reports" in sql
    assert "public_validation_report_id" in sql
    assert "validation_reports_output_created_idx" in sql
    assert "regeneration_idempotency_key" in sql
    assert "previous_output_id" in sql


# ===== from test_validation_feedback_security.py =====
from orchestrator.app.validation_feedback.service import normalize_validation_sources


def test_validation_source_summary_does_not_expose_artifact_or_secret_fields():
    source = normalize_validation_sources(
        {
            "final_image_path": "data/outputs/job/final.png",
            "bucket": "private",
            "object_key": "workspaces/ws/object.png",
            "signed_url": "https://signed.example",
            "api_key": "sk-secret",
            "ocr_gate": {"background": {"decision": "pass", "raw_response": {"token": "x"}}},
        },
        {},
    )

    text = str(source)
    assert "data/outputs" not in text
    assert "object.png" not in text
    assert "sk-secret" not in text
    assert "raw_response" not in text


# ===== from test_validation_feedback_service.py =====
from contextlib import contextmanager

from orchestrator.app.validation_feedback.service import build_validation_summary_from_output_row, create_validation_report_for_output, normalize_validation_sources


@contextmanager
def _fake_tx():
    yield object()


def test_validation_summary_uses_existing_result_payload_sources():
    row = {
        "result_payload": {
            "ocr_gate": {
                "background": {"decision": "retry_image", "fake_text": True, "unexpected_text_count": 1},
                "final": {"decision": "pass"},
            },
            "validation_summary": {"safe_area": {"overall_pass": False, "score": 0.4}},
        },
        "metadata": {},
    }

    summary = build_validation_summary_from_output_row(row)

    assert summary.status == "fail"
    assert summary.decision == "retry_image"
    assert [item.value for item in summary.failure_types] == ["fake_text", "unexpected_text", "copy_safe_area"]
    assert summary.suggested_actions[0].code.value == "remove_fake_text"


def test_source_normalization_hides_paths_and_provider_raw_fields():
    source = normalize_validation_sources(
        {
            "final_image_path": "data/outputs/job/final.png",
            "ocr_gate": {"background": {"decision": "pass", "raw_response": {"secret": "x"}}},
        },
        {},
    )

    text = str(source)
    assert "data/outputs" not in text
    assert "raw_response" not in text


def test_missing_validation_sources_require_manual_review():
    summary = build_validation_summary_from_output_row({"result_payload": {}, "metadata": {}})

    assert summary.status == "unavailable"
    assert summary.decision == "manual_review"
    assert [item.value for item in summary.failure_types] == ["provider_unavailable", "manual_review_required"]


def test_metadata_sources_are_used_and_provider_status_reduces_by_severity():
    source = normalize_validation_sources(
        {},
        {
            "ocr_gate": {
                "background": {"status": "pass", "decision": "pass"},
                "final": {"status": "unavailable", "decision": "manual_review"},
            }
        },
    )

    assert source["hasValidationSource"] is True
    assert source["ocr"]["backgroundProviderStatus"] == "pass"
    assert source["ocr"]["finalProviderStatus"] == "unavailable"
    assert source["ocr"]["providerStatus"] == "unavailable"


def test_validation_report_creation_survives_event_recording_failure(monkeypatch):
    updates = []
    monkeypatch.setattr("orchestrator.app.validation_feedback.service.db_transaction", lambda: _fake_tx())
    monkeypatch.setattr(
        "orchestrator.app.validation_feedback.service.output_repo.get_generation_output_by_public_id",
        lambda **kwargs: {
            "id": "out_uuid",
            "public_output_id": "output_1",
            "workspace_id": "ws",
            "thread_id": "thread_uuid",
            "job_id": "job_uuid",
            "result_payload": {"ocr_gate": {"background": {"decision": "pass"}, "final": {"decision": "pass"}}},
            "metadata": {},
        },
    )
    monkeypatch.setattr(
        "orchestrator.app.validation_feedback.service.report_repo.create_validation_report",
        lambda **kwargs: {"id": "report_uuid", "public_validation_report_id": "validation_1", **kwargs},
    )
    monkeypatch.setattr(
        "orchestrator.app.validation_feedback.service.output_repo.update_generation_output_validation_summary",
        lambda output_id, **fields: updates.append((output_id, fields)) or {"id": output_id, **fields},
    )
    monkeypatch.setattr(
        "orchestrator.app.validation_feedback.service.event_repo.record_generation_job_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("event failed")),
    )

    result = create_validation_report_for_output(public_output_id="output_1", workspace_id="ws")

    assert result["reportId"] == "validation_1"
    assert updates
