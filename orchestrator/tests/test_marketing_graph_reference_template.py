from pathlib import Path

from PIL import Image

from orchestrator.app.graph.builder import build_marketing_graph


def _base(job_id: str, **extra):
    request = {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "context": {
            "business_type": "cafe",
            "item_or_service": "strawberry cake",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(extra)
    return request


def _image(path: Path) -> str:
    Image.new("RGB", (96, 96), (240, 160, 180)).save(path)
    return str(path)


def test_reference_template_absent_keeps_t2i_only_flow():
    result = build_marketing_graph().invoke(_base("ref-template-none"), config={"configurable": {"thread_id": "ref-template-none"}})

    assert result["status"] == "done"
    assert result["selected_reference_template_id"] is None
    assert result["t2i_request"]["metadata"]["selected_reference_template_id"] is None


def test_direct_reference_image_path_still_runs_reference_preprocess(tmp_path):
    path = _image(tmp_path / "reference.png")

    result = build_marketing_graph().invoke(
        _base("ref-template-direct-path", reference_image_path=path),
        config={"configurable": {"thread_id": "ref-template-direct-path"}},
    )

    assert result["status"] == "done"
    assert result["reference_style_profile"]["metadata"]["vlm_used"] is False
    assert result["t2i_request"]["metadata"]["reference_image_path"] == path


def test_selected_reference_template_reaches_result_and_metadata():
    template_id = "seed_cafe_strawberry_feed_001"

    result = build_marketing_graph().invoke(
        _base("ref-template-selected", selected_reference_template_id=template_id),
        config={"configurable": {"thread_id": "ref-template-selected"}},
    )

    metadata = result["t2i_request"]["metadata"]
    assert result["status"] == "done"
    assert result["selected_reference_template"]["template_id"] == template_id
    assert result["current_brief"]["reference_template_selected"] is True
    assert metadata["selected_reference_template_id"] == template_id
    assert metadata["reference_template_selection"]
    assert result["image_prompt_spec"]["metadata"]["selected_reference_template"]
    assert result["image_prompt_spec"]["metadata"]["visual_template_id"]
    assert metadata["reference_template_style_keywords"]
    assert metadata["reference_template_color_palette"]
    assert result["image_prompt_spec"]["must_not_include_text"] is True
    assert "reserved_text_areas" in metadata
    assert metadata["render_text_in_image"] is False


def test_selected_reference_template_no_copy_reaches_result():
    result = build_marketing_graph().invoke(
        _base("ref-template-no-copy", selected_reference_template_id="seed_instagram_feed_minimal_001", copy_generation_mode="no_copy"),
        config={"configurable": {"thread_id": "ref-template-no-copy"}},
    )

    assert result["status"] == "done"
    assert result["copy_spec"]["copy_mode"] == "no_copy"
    assert result["result_payload"]["has_text_overlay"] is False
    assert result["t2i_request"]["metadata"]["selected_reference_template_id"] == "seed_instagram_feed_minimal_001"
