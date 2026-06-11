from scripts._actual_creative_pipeline import ActualCreativeInput, resolve_image_use_plan


def test_text_only_uses_generate_from_text(tmp_path):
    request = ActualCreativeInput(case_id="case", input_mode="text_only", user_text="cheesecake", output_dir=str(tmp_path))

    plan = resolve_image_use_plan(request, {"visual_observations": []}, {})

    assert plan.mode == "generate_from_text"


def test_image_only_can_use_uploaded_background(tmp_path):
    request = ActualCreativeInput(case_id="case", input_mode="image_only", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path))

    plan = resolve_image_use_plan(request, {"visual_observations": [{"kind": "product", "confidence": 0.9}]}, {})

    assert plan.mode == "use_uploaded_as_background"


def test_image_only_low_confidence_regenerates_or_manual_review(tmp_path):
    request = ActualCreativeInput(case_id="case", input_mode="image_only", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path))

    weak_plan = resolve_image_use_plan(request, {"visual_observations": [{"kind": "product", "confidence": 0.55}]}, {})
    low_plan = resolve_image_use_plan(request, {"visual_observations": [{"kind": "product", "confidence": 0.2}]}, {})

    assert weak_plan.mode == "analyze_then_regenerate"
    assert low_plan.mode == "manual_review"


def test_conflict_requires_manual_review(tmp_path):
    request = ActualCreativeInput(case_id="case", input_mode="text_and_image", user_text="cheesecake", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path))

    plan = resolve_image_use_plan(request, {"input_conflicts": [{"field": "product"}], "visual_observations": [{"confidence": 0.9}]}, {})

    assert plan.mode == "manual_review"


def test_missing_confidence_manual_review(tmp_path):
    request = ActualCreativeInput(case_id="case", input_mode="image_only", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path))

    plan = resolve_image_use_plan(request, {"visual_observations": [{"kind": "product"}]}, {})

    assert plan.mode == "manual_review"
