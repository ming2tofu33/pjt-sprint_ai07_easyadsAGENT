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
