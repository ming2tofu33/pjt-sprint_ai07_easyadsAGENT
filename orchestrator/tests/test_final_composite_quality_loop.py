from __future__ import annotations

from pathlib import Path

from PIL import Image

from orchestrator.app.graph.routers import route_after_final_composite_revision, route_after_final_validation
from orchestrator.app.llm.nodes.final_composite_revision import final_composite_revision_node
from orchestrator.app.llm.nodes.final_copy_revision import final_copy_revision_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite


def _image(path: Path, color: str = "#f5f1ea") -> str:
    Image.new("RGB", (1000, 1000), color).save(path)
    return str(path)


def _base_state(path: str) -> dict:
    traces = [
        {"role": "headline", "text": "Fresh Menu", "effective_font_size_px": 80, "rendered_lines": ["Fresh Menu"], "rendered_bbox_px": [100, 120, 520, 220], "contrast_ratio_min": 6.0},
        {"role": "body", "text": "Soft seasonal desserts", "effective_font_size_px": 32, "rendered_lines": ["Soft seasonal desserts"], "rendered_bbox_px": [100, 250, 520, 310], "contrast_ratio_min": 6.0},
        {"role": "cta", "text": "Order now", "effective_font_size_px": 28, "rendered_lines": ["Order now"], "rendered_bbox_px": [100, 340, 280, 390], "contrast_ratio_min": 6.0},
    ]
    return {
        "background_validation_report": {"overall_pass": True},
        "safe_area_report": {"overall_pass": True},
        "readability_report": {"overall_pass": True},
        "render_result": {"final_image_path": path, "rendered_slot_count": 3, "metadata": {"typography_render_traces": traces}},
        "artifact_refs": [{"type": "final_image", "path": path}],
        "marketing_copy": {"headline": "Fresh Menu", "subcopy": "Soft seasonal desserts", "cta": "Order now"},
        "final_ocr_gate": {"status": "pass", "ocr": {"detected_text": ["Fresh Menu", "Soft seasonal desserts", "Order now"], "missing_text_count": 0, "extra_text_count": 0}},
    }


def test_final_composite_uses_render_result_final_path_only(tmp_path):
    final_path = _image(tmp_path / "final.png")
    wrong_path = _image(tmp_path / "wrong.png", "#000000")
    state = _base_state(final_path)
    state["final_image_path"] = wrong_path

    report = evaluate_final_composite(state)

    assert report.evaluated_image_path == final_path
    assert "final_image_contract_mismatch" in report.failure_types


def test_final_composite_passes_clean_composite(tmp_path):
    state = _base_state(_image(tmp_path / "final.png"))

    report = evaluate_final_composite(state)

    assert report.status == "pass"
    assert report.primary_action == "none"
    assert report.deterministic_metrics.headline_body_size_ratio > 1.5


def test_final_composite_cta_dominance_reduces_cta(tmp_path):
    state = _base_state(_image(tmp_path / "final.png"))
    state["render_result"]["metadata"]["typography_render_traces"][2]["effective_font_size_px"] = 72
    state["render_result"]["metadata"]["typography_render_traces"][2]["rendered_bbox_px"] = [80, 300, 920, 520]

    report = evaluate_final_composite(state)

    assert "cta_dominance" in report.failure_types
    assert report.primary_action == "reduce_cta_emphasis"
    assert report.status == "revise"


def test_final_validation_embeds_composite_report(tmp_path):
    state = _base_state(_image(tmp_path / "final.png"))

    result = final_validation_node(state)

    assert result["final_validation_report"]["overall_pass"] is True
    assert result["final_composite_quality_report"]["status"] == "pass"
    assert result["final_validation_report"]["metadata"]["final_composite_quality"]["status"] == "pass"


def test_final_composite_revision_routes_style_retry():
    state = {
        "final_composite_quality_report": {"status": "revise", "primary_action": "reduce_cta_emphasis", "retry_feedback": ["final_composite:cta_dominance"]},
        "final_composite_attempts": 0,
    }

    update = final_composite_revision_node(state)

    assert update["final_composite_revision_plan"]["rerun_from_node"] == "adaptive_typography_refiner"
    assert update["final_style_revision_attempts"] == 1
    assert "t2i_result" in update["final_composite_revision_plan"]["preserved_fields"]
    assert route_after_final_composite_revision(update) == "adaptive_typography_refiner"


def test_final_composite_router_revises_only_revise_status():
    assert route_after_final_validation({"final_composite_quality_report": {"status": "revise"}}) == "final_composite_revision"
    assert route_after_final_validation({"final_composite_quality_report": {"status": "manual_review"}}) == "result"


def test_final_composite_vlm_unavailable_not_pass_in_actual_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYADS_FINAL_COMPOSITE_ACTUAL", "1")
    state = _base_state(_image(tmp_path / "final.png"))
    state.pop("final_composite_vlm_result", None)

    report = evaluate_final_composite(state)

    assert report.status == "manual_review"
    assert "provider_unavailable" in report.failure_types


def test_final_copy_revision_changes_copy_and_skips_t2i():
    update = final_copy_revision_node(
        {
            "marketing_copy": {
                "headline": "Macaron Collection Best Quality Limited Time",
                "subcopy": "부드러운 색감과 달콤한 한 입으로 고르는 프렌치 마카롱 컬렉션",
                "cta": "메뉴 자세히 보기",
            },
            "final_composite_revision_plan": {"action": "shorten_copy"},
        }
    )

    assert update["marketing_copy"]["headline"] != "Macaron Collection Best Quality Limited Time"
    assert update["final_copy_revision_result"]["t2i_bypass"] is True
    assert update["reuse_existing_background"] is True


def test_reduce_cta_patch_changes_render_trace():
    update = final_composite_revision_node(
        {
            "final_composite_quality_report": {"status": "revise", "primary_action": "reduce_cta_emphasis", "failure_types": ["cta_dominance"]},
        }
    )

    assert update["final_composite_revision_patch"]["cta_scale_delta"] < 0
    assert update["final_composite_revision_plan"]["rerun_from_node"] == "adaptive_typography_refiner"
