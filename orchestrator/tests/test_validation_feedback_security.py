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
