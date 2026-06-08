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

