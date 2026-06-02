from pathlib import Path

import pytest
from langgraph.types import Command
from PIL import Image
from pydantic import ValidationError

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.routers import route_by_copy_presence
from orchestrator.app.llm.nodes.background_validation import background_validation_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.llm.nodes.readability_gate import average_region_rgb, contrast_ratio, readability_gate_node, relative_luminance
from orchestrator.app.llm.nodes.result import result_node
from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
from orchestrator.app.llm.nodes.text_renderer import SYSTEM_FONT_CANDIDATES, text_renderer_node
from orchestrator.app.schemas.text_layout import (
    BackgroundValidationReport,
    CopyItem,
    CopySpec,
    FinalValidationReport,
    FontMetric,
    NormalizedBBox,
    ReadabilityReport,
    RenderResult,
    ResultPayload,
    SafeAreaReport,
    SlotReadability,
    TextLayoutSpec,
    TextSlot,
    TextStyleSpec,
    TypographyRule,
)


def _image(path: Path, size=(320, 320), color=(30, 30, 30)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return str(path)


def _style() -> dict:
    return TextStyleSpec(
        profile="clean",
        typography=TypographyRule(
            headline_font="Pretendard-Bold",
            body_font="Pretendard-Regular",
            headline_weight=700,
            body_weight=400,
            headline_size_ratio=0.07,
            body_size_ratio=0.035,
            primary_color="#111827",
            accent_color="#3B82F6",
            text_color_on_light="#111827",
            text_color_on_dark="#FFFFFF",
            default_overlay="drop_shadow",
        ),
    ).model_dump()


def _layout(overlap: bool = False) -> dict:
    product = NormalizedBBox(x=0.15, y=0.36, w=0.70, h=0.42)
    headline_box = NormalizedBBox(x=0.05, y=0.06, w=0.90, h=0.18)
    if overlap:
        headline_box = NormalizedBBox(x=0.20, y=0.40, w=0.50, h=0.16)
    return TextLayoutSpec(
        template="top_headline_center_product_bottom_cta",
        canvas_width=320,
        canvas_height=320,
        slots=[
            TextSlot(
                slot_id="slot_headline",
                role="headline",
                bbox=headline_box,
                rendered_text="Hello BBQ",
                font_metric=FontMetric(base_size_ratio=0.07, min_size_ratio=0.03, max_size_ratio=0.10, weight=700),
                text_color="#FFFFFF",
            )
        ],
        product_zone=product,
    ).model_dump()


def _copy_spec() -> dict:
    return CopySpec(items=[CopyItem(role="headline", text="Hello BBQ", priority=1)]).model_dump()


def _state(image_path: str, job_id: str = "tlfp-final-test") -> dict:
    layout = _layout()
    return {
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "copy_required": True,
        "text_overlay_pending": True,
        "copy_spec": _copy_spec(),
        "text_layout_spec": layout,
        "text_style_spec": _style(),
        "image_prompt_spec": {"reserved_text_areas": layout["reserved_text_areas"]},
        "t2i_request": {
            "prompt": "mock",
            "negative_prompt": "text",
            "width": 320,
            "height": 320,
            "metadata": {"render_text_in_image": False, "reserved_text_areas": layout["reserved_text_areas"]},
        },
        "t2i_result": {"engine": "mock", "image_paths": [image_path], "width": 320, "height": 320},
        "artifact_refs": [],
    }


def test_final_pipeline_schemas_validate():
    slot = SlotReadability(
        slot_id="slot_headline",
        role="headline",
        background_luminance=0.1,
        text_luminance=1.0,
        contrast_ratio=8.0,
        wcag_grade="AAA",
        suggested_action="none",
    )
    assert ReadabilityReport(overall_pass=True, slots=[slot], avg_contrast_ratio=8.0, min_contrast_ratio=8.0, failed_slot_count=0)
    assert BackgroundValidationReport(overall_pass=True, image_exists=True, render_text_in_image=False, reserved_text_area_count=1)
    assert SafeAreaReport(overall_pass=True, reserved_text_area_count=1)
    assert RenderResult(background_image_path="a.png", final_image_path="b.png", rendered_slot_count=1, skipped_slot_count=0)
    assert FinalValidationReport(overall_pass=True, background_pass=True, safe_area_pass=True, readability_pass=True, no_copy=False)
    assert ResultPayload(job_id="job", thread_id="thread", status="done", has_text_overlay=True)
    with pytest.raises(ValidationError):
        SlotReadability(slot_id="bad", role="headline", background_luminance=-0.1, text_luminance=1.0, contrast_ratio=1, wcag_grade="FAIL")


def test_background_validation_node_checks_image_and_artifacts(tmp_path):
    image_path = _image(tmp_path / "background.png")
    state = _state(image_path)
    output = background_validation_node(state)

    report = output["background_validation_report"]
    assert report["overall_pass"] is True
    assert report["image_exists"] is True
    assert report["width"] == 320
    assert report["reserved_text_area_count"] == 1
    assert report["text_artifact_check"] == "not_run"
    vlm_contract = report["metadata"]["vlm_metadata_contract"]
    assert vlm_contract["available_state"]["image_paths"] == [image_path]
    assert vlm_contract["available_state"]["reserved_text_areas"] == state["text_layout_spec"]["reserved_text_areas"]
    assert vlm_contract["constraints"]["ocr_or_vlm_called"] is False
    assert vlm_contract["constraints"]["vlm_call_allowed"] is False
    assert report["metadata"]["validation_questions"]
    assert output["artifact_refs"][-1]["type"] == "background_image"


def test_background_validation_missing_image_fails():
    output = background_validation_node(_state("missing.png"))

    assert output["background_validation_report"]["overall_pass"] is False
    assert output["background_validation_report"]["image_exists"] is False


def test_safe_area_gate_reports_overlap_and_no_copy_passes():
    state = _state("unused.png")
    state["text_layout_spec"] = _layout(overlap=True)
    output = safe_area_gate_node(state)

    assert output["safe_area_report"]["overall_pass"] is False
    assert output["safe_area_report"]["bbox_issues"]

    no_copy_state = {
        **state,
        "copy_generation_mode": "no_copy",
        "copy_required": False,
        "copy_spec": {"copy_mode": "no_copy", "items": []},
        "text_layout_spec": TextLayoutSpec(template="no_text", canvas_width=320, canvas_height=320, slots=[], reserved_text_areas=[]).model_dump(),
    }
    no_copy_output = safe_area_gate_node(no_copy_state)
    assert no_copy_output["safe_area_report"]["overall_pass"] is True
    assert no_copy_output["safe_area_report"]["reserved_text_area_count"] == 0


def test_copy_presence_router_routes_without_mutation():
    state = {"copy_generation_mode": "no_copy", "copy_required": False, "text_overlay_pending": False, "copy_spec": {"copy_mode": "no_copy"}}
    before = dict(state)

    assert route_by_copy_presence(state) == "result"
    assert state == before
    assert route_by_copy_presence({"copy_required": True, "text_overlay_pending": True, "copy_spec": {"copy_mode": "standard"}}) == "text_renderer"


def test_text_renderer_creates_final_image(tmp_path):
    image_path = _image(tmp_path / "background.png")
    output = text_renderer_node(_state(image_path, "text-render-node-test"))

    final_path = Path(output["final_image_path"])
    assert final_path.exists()
    assert final_path.name == "final_composite.png"
    assert output["render_result"]["rendered_slot_count"] == 1
    assert output["text_overlay_pending"] is False
    assert output["artifact_refs"][-1]["type"] == "final_image"


def test_text_renderer_has_cross_platform_korean_font_candidates():
    assert any("malgun" in candidate.lower() for candidate in SYSTEM_FONT_CANDIDATES)
    assert any("nanum" in candidate.lower() or "notosanscjk" in candidate.lower() or "unifont" in candidate.lower() for candidate in SYSTEM_FONT_CANDIDATES)


def test_readability_helpers_and_gate(tmp_path):
    assert relative_luminance((0, 0, 0)) == 0
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) > 20
    image_path = _image(tmp_path / "background.png", color=(0, 0, 0))
    with Image.open(image_path) as image:
        assert average_region_rgb(image, (0, 0, 10, 10)) == (0, 0, 0)

    output = readability_gate_node(_state(image_path))
    report = output["readability_report"]
    assert report["slots"]
    assert report["failed_slot_count"] == 0
    assert report["overall_pass"] is True


def test_final_validation_and_result_nodes(tmp_path):
    image_path = _image(tmp_path / "background.png")
    state = {
        **_state(image_path, "final-result-test"),
        "background_validation_report": {"overall_pass": True},
        "safe_area_report": {"overall_pass": True},
        "readability_report": {"overall_pass": True},
        "final_image_path": str(tmp_path / "final.png"),
        "artifact_refs": [],
    }
    _image(Path(state["final_image_path"]))
    final_output = final_validation_node(state)
    final_report = final_output["final_validation_report"]
    assert final_report["overall_pass"] is True
    vlm_contract = final_report["metadata"]["vlm_metadata_contract"]
    assert vlm_contract["available_state"]["final_image_path"] == state["final_image_path"]
    assert vlm_contract["available_state"]["expected_copy"] == [{"role": "headline", "text": "Hello BBQ"}]
    assert vlm_contract["constraints"]["ocr_or_vlm_called"] is False
    assert vlm_contract["constraints"]["vlm_call_allowed"] is False
    assert final_report["metadata"]["validation_questions"]

    result_output = result_node({**state, **final_output, "text_overlay_pending": False})
    assert result_output["result_payload"]["status"] == "done"
    assert result_output["result_payload"]["has_text_overlay"] is True
    assert result_output["artifact_refs"][-1]["type"] == "result_image"


def test_result_node_no_copy_uses_background(tmp_path):
    image_path = _image(tmp_path / "background.png")
    output = result_node(
        {
            **_state(image_path, "result-no-copy-test"),
            "copy_generation_mode": "no_copy",
            "copy_required": False,
            "text_overlay_pending": False,
            "copy_spec": {"copy_mode": "no_copy", "items": []},
        }
    )

    assert output["result_payload"]["output_path"] == image_path
    assert output["result_payload"]["has_text_overlay"] is False


def _graph_request(mode: str, job_id: str) -> dict:
    return {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": mode,
        "context": {
            "business_type": "restaurant",
            "item_or_service": "BBQ",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }


def test_marketing_graph_final_result_auto_pilot_and_no_copy():
    auto = build_marketing_graph().invoke(_graph_request("auto_pilot", "final-auto-pilot"), config={"configurable": {"thread_id": "final-auto-pilot"}})
    assert auto["status"] == "done"
    assert auto["result_payload"]["output_path"]
    assert auto["result_payload"]["has_text_overlay"] is True
    assert auto["background_validation_report"]
    assert auto["safe_area_report"]
    assert auto["readability_report"]
    assert auto["final_validation_report"]

    no_copy = build_marketing_graph().invoke(_graph_request("no_copy", "final-no-copy"), config={"configurable": {"thread_id": "final-no-copy"}})
    assert no_copy["status"] == "done"
    assert no_copy["result_payload"]["output_path"] == no_copy["t2i_result"]["image_paths"][0]
    assert no_copy["result_payload"]["has_text_overlay"] is False
    assert no_copy.get("readability_report") is None
    no_copy_vlm_contract = no_copy["background_validation_report"]["metadata"]["vlm_metadata_contract"]
    assert no_copy_vlm_contract["constraints"]["render_text_in_image"] is False
    assert no_copy_vlm_contract["constraints"]["ocr_or_vlm_called"] is False


def test_marketing_graph_final_result_suggest_and_custom():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "final-suggest"}}
    first = graph.invoke(_graph_request("suggest_candidates", "final-suggest"), config=config)
    assert first["__interrupt__"][0].value["type"] == "copy_candidate_selection"
    suggest = graph.invoke(Command(resume={"selected_copy_id": "copy_1"}), config=config)
    assert suggest["status"] == "done"
    assert suggest["result_payload"]["has_text_overlay"] is True

    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "final-custom"}}
    first = graph.invoke(_graph_request("custom_input", "final-custom"), config=config)
    assert first["__interrupt__"][0].value["type"] == "custom_copy_input"
    custom = graph.invoke(Command(resume={"user_custom_headline": "Custom headline"}), config=config)
    assert custom["status"] == "done"
    assert custom["marketing_copy"]["headline"] == "Custom headline"
    assert custom["result_payload"]["has_text_overlay"] is True
