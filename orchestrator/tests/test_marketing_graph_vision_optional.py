from pathlib import Path

from PIL import Image

from orchestrator.app.graph.builder import build_marketing_graph


def _image(path: Path, color=(180, 120, 90)) -> Path:
    Image.new("RGB", (96, 96), color).save(path)
    return path


def _request(job_id: str, **extra):
    request = {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": "restaurant",
            "item_or_service": "cake",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(extra)
    return request


def test_marketing_graph_without_image_path_keeps_t2i_only_route():
    result = build_marketing_graph().invoke(_request("vision-none"), config={"configurable": {"thread_id": "vision-none"}})

    assert result["status"] == "done"
    assert result["vision_pipeline_results"] == []
    assert result["t2i_request"]["metadata"]["vision_pipeline_enabled"] is False


def test_marketing_graph_with_source_image_runs_product_preprocess_to_result(tmp_path):
    source = _image(tmp_path / "source.png")

    result = build_marketing_graph().invoke(
        _request("vision-source", source_image_path=str(source)),
        config={"configurable": {"thread_id": "vision-source"}},
    )

    metadata = result["t2i_request"]["metadata"]
    assert result["status"] == "done"
    assert result["product_preserve_spec"]["preserve_strategy"] == "center_bbox_stub"
    assert result["current_brief"]["product_preserve_ready"] is True
    assert metadata["vision_pipeline_enabled"] is True
    assert metadata["source_image_path"] == str(source)
    assert metadata["product_preserve_spec"]["metadata"]["sam_used"] is False
    assert result["result_payload"]["output_path"]


def test_marketing_graph_with_reference_image_runs_reference_preprocess_to_result(tmp_path):
    reference = _image(tmp_path / "reference.png", color=(240, 120, 160))

    result = build_marketing_graph().invoke(
        _request("vision-reference", reference_image_path=str(reference)),
        config={"configurable": {"thread_id": "vision-reference"}},
    )

    metadata = result["t2i_request"]["metadata"]
    assert result["status"] == "done"
    assert result["reference_style_profile"]["metadata"]["vlm_used"] is False
    assert result["current_brief"]["reference_style_ready"] is True
    assert metadata["vision_pipeline_enabled"] is True
    assert metadata["reference_image_path"] == str(reference)
    assert "reference-inspired" in result["image_prompt_spec"]["positive_prompt_en"]


def test_no_copy_with_source_image_bypasses_text_renderer_and_reaches_result(tmp_path):
    source = _image(tmp_path / "source-no-copy.png")
    request = _request("vision-no-copy", source_image_path=str(source), copy_generation_mode="no_copy")

    result = build_marketing_graph().invoke(request, config={"configurable": {"thread_id": "vision-no-copy"}})

    assert result["status"] == "done"
    assert result["copy_spec"]["copy_mode"] == "no_copy"
    assert result["render_result"] is None
    assert result["result_payload"]["has_text_overlay"] is False
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
