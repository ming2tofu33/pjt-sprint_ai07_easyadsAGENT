from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.types import Command
from PIL import Image

import orchestrator.app.graph.builder as graph_builder
from orchestrator.app.ocr_gate.schemas import OCRValidationResult


TRACEABLE_NODE_ATTRS = {
    "input": "input_node",
    "reference_template_resolve": "reference_template_resolve_node",
    "product_preprocess": "product_preprocess_node",
    "reference_preprocess": "reference_preprocess_node",
    "validator": "validator_node",
    "options": "options_node",
    "state_update": "state_update_node",
    "format_planner": "format_planner_node",
    "tone_binding": "tone_binding_node",
    "copy_candidate_generation": "copy_candidate_generation_node",
    "copy_candidate_selection_interrupt": "copy_candidate_selection_interrupt_node",
    "state_update_selected_copy": "state_update_selected_copy_node",
    "auto_pilot_copywriting": "auto_pilot_copywriting_node",
    "custom_copy_input": "custom_copy_input_interrupt_node",
    "custom_copy_validation": "custom_copy_validation_node",
    "input_compliance_precheck": "input_compliance_precheck_node",
    "no_copy_bypass": "no_copy_bypass_node",
    "copy_compliance_gate": "copy_compliance_gate_node",
    "copy_compliance_interrupt": "copy_compliance_interrupt_node",
    "copy_compliance_resolution": "copy_compliance_resolution_node",
    "copy_spec_parser": "copy_spec_parser_node",
    "typography_art_direction": "typography_art_direction_node",
    "text_style_binder": "text_style_binder_node",
    "text_layout_planner": "text_layout_planner_node",
    "image_prompt_planner": "image_prompt_planner_node",
    "prompt_renderer": "prompt_renderer_node",
    "t2i_request_builder": "t2i_request_builder_node",
    "t2i_generation": "t2i_generation_node",
    "background_ocr_gate": "background_ocr_gate_node",
    "ocr_image_revision": "ocr_image_revision_node",
    "background_validation": "background_validation_node",
    "image_layout_analyzer": "image_layout_analyzer_node",
    "post_t2i_layout_refiner": "post_t2i_layout_refiner_node",
    "adaptive_typography_refiner": "adaptive_typography_refiner_node",
    "safe_area_gate": "safe_area_gate_node",
    "text_renderer": "text_renderer_node",
    "html_text_renderer": "html_text_renderer_node",
    "image_analysis": "image_analysis_node",
    "poster_layout_planner": "poster_layout_planner_node",
    "poster_renderer": "poster_renderer_node",
    "image_aware_quality_gate": "image_aware_quality_gate_node",
    "design_recommendation": "design_recommendation_node",
    "final_ocr_gate": "final_ocr_gate_node",
    "ocr_layout_revision": "ocr_layout_revision_node",
    "readability_gate": "readability_gate_node",
    "final_validation": "final_validation_node",
    "result": "result_node",
}


NODE_UTILIZATION_MATRIX = {
    "missing_context_question": {
        "includes": ["input", "validator", "options", "state_update"],
        "excludes": ["format_planner", "input_compliance_precheck", "t2i_generation", "result"],
    },
    "auto_pilot_text_overlay": {
        "includes": [
            "input",
            "validator",
            "input_compliance_precheck",
            "format_planner",
            "tone_binding",
            "auto_pilot_copywriting",
            "copy_compliance_gate",
            "copy_spec_parser",
            "typography_art_direction",
            "image_layout_analyzer",
            "post_t2i_layout_refiner",
            "adaptive_typography_refiner",
            "text_renderer",
            "final_ocr_gate",
            "readability_gate",
            "final_validation",
            "result",
        ],
        "excludes": ["copy_candidate_generation", "custom_copy_input", "no_copy_bypass"],
    },
    "html_text_overlay": {
        "includes": [
            "input",
            "validator",
            "format_planner",
            "tone_binding",
            "auto_pilot_copywriting",
            "copy_spec_parser",
            "html_text_renderer",
            "final_ocr_gate",
            "readability_gate",
            "final_validation",
            "result",
        ],
        "excludes": ["text_renderer", "image_analysis", "poster_renderer"],
    },
    "poster_components": {
        "includes": [
            "input",
            "validator",
            "format_planner",
            "tone_binding",
            "auto_pilot_copywriting",
            "copy_spec_parser",
            "image_analysis",
            "poster_layout_planner",
            "poster_renderer",
            "image_aware_quality_gate",
            "design_recommendation",
            "readability_gate",
            "final_validation",
            "result",
        ],
        "excludes": ["text_renderer", "html_text_renderer"],
    },
    "photo_suggest_candidates": {
        "includes": [
            "input",
            "product_preprocess",
            "input_compliance_precheck",
            "copy_candidate_generation",
            "copy_candidate_selection_interrupt",
            "state_update_selected_copy",
            "copy_compliance_gate",
            "t2i_request_builder",
            "t2i_generation",
            "background_ocr_gate",
            "image_layout_analyzer",
            "post_t2i_layout_refiner",
            "adaptive_typography_refiner",
            "result",
        ],
        "excludes": ["reference_template_resolve", "custom_copy_input", "no_copy_bypass"],
    },
    "custom_copy_direct": {
        "includes": ["input_compliance_precheck", "custom_copy_input", "custom_copy_validation", "copy_compliance_gate", "copy_spec_parser", "typography_art_direction", "adaptive_typography_refiner", "text_renderer", "result"],
        "excludes": ["copy_candidate_generation", "auto_pilot_copywriting", "no_copy_bypass"],
    },
    "no_copy_image_only": {
        "includes": ["input_compliance_precheck", "no_copy_bypass", "copy_spec_parser", "typography_art_direction", "image_layout_analyzer", "post_t2i_layout_refiner", "adaptive_typography_refiner", "safe_area_gate", "result"],
        "excludes": ["text_renderer", "final_ocr_gate", "readability_gate", "final_validation"],
    },
    "reference_template": {
        "includes": ["input_compliance_precheck", "reference_template_resolve", "image_prompt_planner", "t2i_request_builder", "image_layout_analyzer", "post_t2i_layout_refiner", "adaptive_typography_refiner", "result"],
        "excludes": ["product_preprocess", "reference_preprocess"],
    },
    "reference_image": {
        "includes": ["input_compliance_precheck", "reference_preprocess", "image_prompt_planner", "t2i_request_builder", "image_layout_analyzer", "post_t2i_layout_refiner", "adaptive_typography_refiner", "result"],
        "excludes": ["product_preprocess", "reference_template_resolve"],
    },
    "ocr_revision_loop": {
        "includes": ["input_compliance_precheck", "background_ocr_gate", "ocr_image_revision", "final_ocr_gate", "ocr_layout_revision", "copy_compliance_gate", "result"],
        "excludes": ["copy_candidate_generation", "custom_copy_input", "no_copy_bypass"],
    },
    "compliance_blocked_and_resolved": {
        "includes": [
            "input_compliance_precheck",
            "custom_copy_input",
            "custom_copy_validation",
            "copy_compliance_gate",
            "copy_compliance_interrupt",
            "copy_compliance_resolution",
            "copy_spec_parser",
            "result",
        ],
        "excludes": ["copy_candidate_generation", "auto_pilot_copywriting", "no_copy_bypass"],
    },
}


def _base_request(job_id: str, copy_generation_mode: str = "auto_pilot", **extra: Any) -> dict[str, Any]:
    request = {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": copy_generation_mode,
        "context": {
            "business_type": "cafe",
            "item_or_service": "딸기라떼",
            "promotion_goal": "discount_event",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(extra)
    return request


def _make_image(path: Path, color: tuple[int, int, int] = (230, 90, 130)) -> str:
    Image.new("RGB", (96, 96), color).save(path)
    return str(path)


def _state_request(job_id: str, copy_generation_mode: str = "auto_pilot", **extra: Any) -> dict[str, Any]:
    request = _base_request(job_id, copy_generation_mode=copy_generation_mode, **extra)
    request.update(
        {
            "schema_version": "llm_marketing_v1",
            "engine": "mock",
            "copy_required": copy_generation_mode != "no_copy",
            "text_overlay_pending": copy_generation_mode != "no_copy",
        }
    )
    return request


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _build_traced_marketing_graph(monkeypatch):
    trace: list[str] = []

    def wrap(node_name: str, original):
        def traced_node(state, *args, **kwargs):
            trace.append(node_name)
            return original(state, *args, **kwargs)

        traced_node.__name__ = getattr(original, "__name__", node_name)
        return traced_node

    for node_name, attr_name in TRACEABLE_NODE_ATTRS.items():
        monkeypatch.setattr(graph_builder, attr_name, wrap(node_name, getattr(graph_builder, attr_name)))

    return graph_builder.build_marketing_graph(), trace


def _capture(trace: list[str], action):
    start = len(trace)
    result = action()
    return trace[start:], result


def _run_missing_context_question(graph, trace: list[str]):
    def action():
        thread_id = "node-matrix-missing-context"
        first = graph.invoke(
            {"user_input": "광고 만들어줘", "job_id": thread_id, "thread_id": thread_id},
            config=_config(thread_id),
        )
        payload = first["__interrupt__"][0].value
        return graph.invoke(
            Command(
                resume={
                    "job_id": payload["job_id"],
                    "thread_id": payload["thread_id"],
                    "field": payload["option_question"]["field"],
                    "value": "cafe",
                }
            ),
            config=_config(thread_id),
        )

    return _capture(trace, action)[0]


def _run_complete_request(graph, trace: list[str], request: dict[str, Any]):
    return _capture(trace, lambda: graph.invoke(request, config=_config(request["thread_id"])))[0]


def _run_photo_suggest_candidates(graph, trace: list[str], tmp_path: Path):
    def action():
        thread_id = "node-matrix-photo-suggest"
        first = graph.invoke(
            _base_request(
                thread_id,
                copy_generation_mode="suggest_candidates",
                source_image_path=_make_image(tmp_path / "photo-source.png"),
            ),
            config=_config(thread_id),
        )
        assert first["__interrupt__"][0].value["type"] == "copy_candidate_selection"
        return graph.invoke(Command(resume={"selected_copy_id": "copy_1"}), config=_config(thread_id))

    return _capture(trace, action)[0]


def _run_ocr_revision_loop(graph, trace: list[str], monkeypatch):
    calls = {"background": 0, "final_ad": 0}

    def fake_run_ocr_gate(*, request, **kwargs):
        calls[request.stage] += 1
        if request.stage == "background" and calls["background"] == 1:
            return OCRValidationResult(stage="background", provider="fake", status="fail", decision="retry_image", revision_action="retry_image", retry_feedback=["remove fake text"])
        if request.stage == "final_ad" and calls["final_ad"] == 1:
            return OCRValidationResult(stage="final_ad", provider="fake", status="fail", decision="retry_layout", revision_action="retry_layout", retry_feedback=["improve text fit"])
        return OCRValidationResult(stage=request.stage, provider="fake", status="pass", decision="pass")

    monkeypatch.setenv("EASYADS_OCR_GATE_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_REVISION_LOOP_ENABLED", "true")
    monkeypatch.setenv("EASYADS_OCR_MAX_REVISIONS", "2")
    monkeypatch.setattr("orchestrator.app.llm.nodes.ocr_gate.run_ocr_gate", fake_run_ocr_gate)

    return _run_complete_request(graph, trace, _base_request("node-matrix-ocr-revision", copy_generation_mode="auto_pilot"))


def _run_compliance_blocked_and_resolved(graph, trace: list[str]):
    def action():
        thread_id = "node-matrix-compliance-blocked"
        context = {
            "business_type": "beauty_skincare",
            "item_or_service": "스킨케어 크림",
            "promotion_goal": "new_launch",
            "extra": {"ad_format": "instagram_feed"},
        }
        first = graph.invoke(
            {
                "user_input": "ready",
                "job_id": thread_id,
                "thread_id": thread_id,
                "copy_generation_mode": "custom_input",
                "user_custom_headline": "여드름 치료 100% 보장",
                "context": context,
            },
            config=_config(thread_id),
        )
        assert first["__interrupt__"][0].value["type"] == "copy_compliance_review"
        return graph.invoke(
            Command(resume={"action": "keep_original_draft"}),
            config=_config(thread_id),
        )

    return _capture(trace, action)[0]


def _assert_matrix_expectation(scenario: str, trace: list[str]) -> None:
    expectation = NODE_UTILIZATION_MATRIX[scenario]
    missing = [node for node in expectation["includes"] if node not in trace]
    unexpected = [node for node in expectation["excludes"] if node in trace]
    assert missing == [], f"{scenario} did not execute expected nodes: {missing}; trace={trace}"
    assert unexpected == [], f"{scenario} executed excluded nodes: {unexpected}; trace={trace}"


def test_marketing_graph_node_utilization_matrix_covers_all_nodes(monkeypatch, tmp_path):
    graph, trace = _build_traced_marketing_graph(monkeypatch)
    scenario_traces = {
        "missing_context_question": _run_missing_context_question(graph, trace),
        "auto_pilot_text_overlay": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-auto-pilot", copy_generation_mode="auto_pilot"),
        ),
        "html_text_overlay": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-html", copy_generation_mode="auto_pilot", rendering_engine="html"),
        ),
        "poster_components": _run_complete_request(
            graph,
            trace,
            _base_request(
                "node-matrix-poster-components",
                copy_generation_mode="auto_pilot",
                renderer_mode="poster_components",
                render_profile="fast",
            ),
        ),
        "photo_suggest_candidates": _run_photo_suggest_candidates(graph, trace, tmp_path),
        "custom_copy_direct": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-custom-direct", copy_generation_mode="custom_input", user_custom_headline="직접 준비한 문구"),
        ),
        "no_copy_image_only": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-no-copy", copy_generation_mode="no_copy"),
        ),
        "reference_template": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-reference-template", selected_reference_template_id="seed_cafe_strawberry_feed_001"),
        ),
        "reference_image": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-reference-image", reference_image_path=_make_image(tmp_path / "reference.png", color=(120, 160, 240))),
        ),
        "ocr_revision_loop": _run_ocr_revision_loop(graph, trace, monkeypatch),
        "compliance_blocked_and_resolved": _run_compliance_blocked_and_resolved(graph, trace),
    }

    for scenario, scenario_trace in scenario_traces.items():
        _assert_matrix_expectation(scenario, scenario_trace)

    graph_node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    covered_nodes = {node for scenario_trace in scenario_traces.values() for node in scenario_trace}
    assert covered_nodes == graph_node_names
