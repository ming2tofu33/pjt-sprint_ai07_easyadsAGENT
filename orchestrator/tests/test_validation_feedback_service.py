from orchestrator.app.validation_feedback.service import build_validation_summary_from_output_row, normalize_validation_sources


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

