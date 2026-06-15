"""Consolidated marketing graph tests.

Merged from:
- orchestrator/tests/test_marketing_graph_copy_modes_tlfp.py
- orchestrator/tests/test_marketing_graph_e2e_mock.py
- orchestrator/tests/test_marketing_graph_node_utilization.py
- orchestrator/tests/test_marketing_graph_reference_template.py
- orchestrator/tests/test_marketing_graph_tlfp_mock.py
- orchestrator/tests/test_marketing_graph_vision_optional.py
"""

from __future__ import annotations



# ===== from test_marketing_graph_copy_modes_tlfp.py =====
from langgraph.types import Command

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext
from orchestrator.tests.factories.marketing_state import make_marketing_request
from orchestrator.tests.helpers.images import write_test_png


def _request(mode: str, job_id: str):
    return make_marketing_request(mode=mode, job_id=job_id)


def test_auto_pilot_mode_runs_through_tlfp_to_mock():
    result = build_marketing_graph().invoke(_request("auto_pilot", "copy-mode-auto"), config={"configurable": {"thread_id": "copy-mode-auto"}})

    assert result["status"] == "done"
    assert result["copy_spec"]["items"][0]["role"] == "headline"
    assert result["t2i_result"]["engine"] == "mock"


def test_no_copy_mode_runs_without_marketing_copy_to_mock():
    result = build_marketing_graph().invoke(_request("no_copy", "copy-mode-none"), config={"configurable": {"thread_id": "copy-mode-none"}})

    assert result["status"] == "done"
    assert result["marketing_copy"] is None
    assert result["copy_spec"]["copy_mode"] == "no_copy"
    assert result["text_layout_spec"]["template"] == "no_text"
    assert result["t2i_request"]["metadata"]["text_overlay_pending"] is False
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
    assert result["t2i_request"]["metadata"]["must_not_include_text"] is True
    assert result["t2i_result"]["engine"] == "mock"


def test_suggest_candidates_interrupt_then_resume_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-suggest"}}
    first = graph.invoke(_request("suggest_candidates", "copy-mode-suggest"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "copy_candidate_selection"
    assert [candidate["id"] for candidate in payload["candidates"]] == ["copy_1", "copy_2"]

    result = graph.invoke(Command(resume={"selected_copy_id": "copy_2"}), config=config)

    assert result["status"] == "done"
    assert result["selected_copy_id"] == "copy_2"
    assert result["copy_spec"]["items"][0]["text"] == "회식은 역시 삼겹살"
    assert result["t2i_result"]["engine"] == "mock"


def test_suggest_candidates_interrupt_accepts_manual_copy_without_selected_id_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-suggest-manual"}}
    first = graph.invoke(_request("suggest_candidates", "copy-mode-suggest-manual"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "copy_candidate_selection"

    result = graph.invoke(
        Command(
            resume={
                "user_custom_headline": "직접 쓴 딸기라떼 광고",
                "user_custom_subcopy": "오늘 오후 한정",
                "selected_channel_id": "instagram-feed",
                "selected_ad_format": "instagram_feed",
                "selected_tone": "감성적인",
            }
        ),
        config=config,
    )

    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "직접 쓴 딸기라떼 광고"
    assert result["marketing_copy"]["subcopy"] == "오늘 오후 한정"
    assert result["marketing_copy"]["metadata"]["copy_resolution"] == "manual_edit"
    assert result["copy_spec"]["items"][0]["text"] == "직접 쓴 딸기라떼 광고"
    assert result["t2i_result"]["engine"] == "mock"


def test_suggest_candidates_with_persisted_selection_skips_interrupt_to_mock():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="copy-mode-suggest-selected",
            thread_id="copy-mode-suggest-selected",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(copy_candidate_generation_node(state))
    state["selected_copy_id"] = "copy_2"
    state["selected_channel_id"] = "instagram-feed"
    state["selected_tone"] = "깔끔한"
    state["custom_direction"] = "문구 여백을 넉넉하게"

    result = build_marketing_graph().invoke(
        state,
        config={"configurable": {"thread_id": "copy-mode-suggest-selected"}},
    )

    assert "__interrupt__" not in result
    assert result["status"] == "done"
    assert result["selected_copy_id"] == "copy_2"
    assert result["copy_spec"]["items"][0]["text"] == "회식은 역시 삼겹살"
    assert result["t2i_result"]["engine"] == "mock"


def test_custom_input_interrupt_then_resume_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-custom"}}
    first = graph.invoke(_request("custom_input", "copy-mode-custom"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "custom_copy_input"

    result = graph.invoke(
        Command(resume={"user_custom_headline": "봄처럼 달콤한 딸기 케이크", "user_custom_subcopy": "이번 주 한정 메뉴"}),
        config=config,
    )

    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "봄처럼 달콤한 딸기 케이크"
    assert result["copy_spec"]["items"][0]["text"] == "봄처럼 달콤한 딸기 케이크"
    assert result["t2i_result"]["engine"] == "mock"


def test_custom_input_with_initial_headline_skips_interrupt():
    request = _request("custom_input", "copy-mode-custom-direct")
    request["user_custom_headline"] = "직접 준비한 문구"
    result = build_marketing_graph().invoke(request, config={"configurable": {"thread_id": "copy-mode-custom-direct"}})

    assert "__interrupt__" not in result
    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "직접 준비한 문구"


# ===== from test_marketing_graph_e2e_mock.py =====
from pathlib import Path

from langgraph.types import Command

from orchestrator.app.graph.builder import build_intake_graph, build_marketing_graph


def test_build_intake_graph_still_interrupts_for_missing_fields():
    graph = build_intake_graph()
    result = graph.invoke(
        {"user_input": "광고 만들어줘", "thread_id": "intake-still-interrupts"},
        config={"configurable": {"thread_id": "intake-still-interrupts"}},
    )

    assert "__interrupt__" in result


def test_marketing_graph_interrupts_when_required_info_is_missing():
    graph = build_marketing_graph()
    result = graph.invoke(
        {"user_input": "광고 만들어줘", "thread_id": "marketing-missing"},
        config={"configurable": {"thread_id": "marketing-missing"}},
    )

    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["type"] == "option_question"


def test_marketing_graph_runs_to_mock_t2i_when_context_is_complete():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-e2e-mock",
            "thread_id": "marketing-e2e-mock",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-e2e-mock"}},
    )

    assert "__interrupt__" not in result
    assert result["status"] == "done"
    for key in [
        "ad_format_spec",
        "layout_spec",
        "marketing_copy",
        "image_prompt",
        "prompt_render_output",
        "t2i_request",
        "t2i_result",
        "candidates",
    ]:
        assert result[key]
    assert result["prompt_render_output"]["engine"] == "mock"
    assert result["t2i_result"]["engine"] == "mock"
    assert result["copy_generation_mode"] == "auto_pilot"
    assert result["copy_spec"]["copy_mode"] == "standard"
    assert result["copy_spec"]["items"][0]["role"] == "headline"
    assert result["text_layout_spec"]["template"]
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
    assert result["t2i_request"]["metadata"]["reserved_text_areas"]
    assert len(result["t2i_request"]["metadata"]["reserved_text_areas"]) == len(result["text_layout_spec"]["reserved_text_areas"])
    assert result["t2i_result"]["image_paths"]
    assert result["t2i_result"]["image_paths"][0].endswith(".png")
    assert result["candidates"][0]["engine"] == "mock"
    image_parts = Path(result["t2i_result"]["image_paths"][0]).parts
    assert "data" in image_parts
    assert "outputs" in image_parts


def test_marketing_graph_resume_continues_to_mock_t2i():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "marketing-resume"}}
    interrupted = graph.invoke(
        {
            "user_input": "우리 삼겹살집 인스타 광고 문구까지 알아서",
            "job_id": "marketing-resume",
            "thread_id": "marketing-resume",
        },
        config=config,
    )
    # copy_generation_mode is now an explicit HITL choice, so the graph may interrupt for
    # more than one field. Answer each asked field until it proceeds to completion.
    resumed = interrupted
    while "__interrupt__" in resumed:
        payload = resumed["__interrupt__"][0].value
        field = payload["option_question"]["field"]
        value = "auto_pilot" if field == "copy_generation_mode" else "reservation_cta"
        resumed = graph.invoke(
            Command(
                resume={
                    "job_id": payload["job_id"],
                    "thread_id": payload["thread_id"],
                    "field": field,
                    "value": value,
                }
            ),
            config=config,
        )

    assert resumed["status"] == "done"
    assert resumed["t2i_result"]["engine"] == "mock"
    assert resumed["copy_generation_mode"] == "auto_pilot"
    assert resumed["copy_spec"]["copy_mode"] == "standard"
    assert resumed["t2i_result"]["image_paths"][0].endswith(".png")


# ===== from test_marketing_graph_node_utilization.py =====
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
    "input_evidence_normalizer": "input_evidence_normalizer_node",
    "product_understanding": "product_understanding_node",
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
    "final_ocr_gate": "final_ocr_gate_node",
    "ocr_layout_revision": "ocr_layout_revision_node",
    "readability_gate": "readability_gate_node",
    "final_validation": "final_validation_node",
    "final_composite_revision": "final_composite_revision_node",
    "final_copy_revision": "final_copy_revision_node",
    "result": "result_node",
}


NODE_UTILIZATION_MATRIX = {
    "missing_context_question": {
        "includes": ["input", "input_evidence_normalizer", "product_understanding", "validator", "options", "state_update"],
        "excludes": ["format_planner", "input_compliance_precheck", "t2i_generation", "result"],
    },
    "auto_pilot_text_overlay": {
        "includes": [
            "input",
            "input_evidence_normalizer",
            "product_understanding",
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
    "photo_suggest_candidates": {
        "includes": [
            "input",
            "product_preprocess",
            "input_evidence_normalizer",
            "product_understanding",
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
    "final_composite_revision": {
        "includes": ["final_composite_revision", "final_copy_revision"],
        "excludes": [],
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
    monkeypatch.chdir(tmp_path)
    graph, trace = _build_traced_marketing_graph(monkeypatch)
    scenario_traces = {
        "missing_context_question": _run_missing_context_question(graph, trace),
        "auto_pilot_text_overlay": _run_complete_request(
            graph,
            trace,
            _base_request("node-matrix-auto-pilot", copy_generation_mode="auto_pilot"),
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
        "final_composite_revision": ["final_composite_revision", "final_copy_revision"],
    }

    for scenario, scenario_trace in scenario_traces.items():
        _assert_matrix_expectation(scenario, scenario_trace)

    graph_node_names = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    covered_nodes = {node for scenario_trace in scenario_traces.values() for node in scenario_trace}
    assert covered_nodes == graph_node_names


# ===== from test_marketing_graph_reference_template.py =====
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


# ===== from test_marketing_graph_tlfp_mock.py =====
from pathlib import Path

from orchestrator.app.graph.builder import build_marketing_graph


def test_marketing_graph_runs_tlfp_to_mock_t2i():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-tlfp-mock",
            "thread_id": "marketing-tlfp-mock",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-tlfp-mock"}},
    )

    assert result["status"] == "done"
    for key in ["copy_spec", "text_layout_spec", "text_style_spec", "image_prompt_spec", "t2i_result"]:
        assert result[key]
    assert result["prompt_render_output"]["metadata"]["tlfp_enabled"] is True
    assert result["t2i_request"]["metadata"]["tlfp_enabled"] is True
    assert result["t2i_request"]["metadata"]["text_layout_spec"]
    assert result["t2i_request"]["metadata"]["image_prompt_spec"]
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
    assert result["t2i_result"]["engine"] == "mock"
    assert result["t2i_result"]["metadata"]["reserved_text_areas"] == result["t2i_request"]["metadata"]["reserved_text_areas"]
    assert result["t2i_result"]["metadata"]["render_text_in_image"] is False
    assert result["t2i_result"]["metadata"]["must_not_include_text"] is True
    image_path = Path(result["t2i_result"]["image_paths"][0])
    assert "data" in image_path.parts
    assert "outputs" in image_path.parts


def test_tlfp_image_prompt_spec_takes_priority_over_legacy_image_prompt():
    graph = build_marketing_graph()
    result = graph.invoke(
        {
            "user_input": "ready",
            "job_id": "marketing-tlfp-priority",
            "thread_id": "marketing-tlfp-priority",
            "copy_generation_mode": "auto_pilot",
            "context": {
                "business_type": "restaurant",
                "item_or_service": "삼겹살",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        },
        config={"configurable": {"thread_id": "marketing-tlfp-priority"}},
    )

    assert result["image_prompt_spec"]["positive_prompt_en"] == result["t2i_request"]["prompt"]
    assert result["image_prompt_spec"]["negative_prompt_en"] == result["t2i_request"]["negative_prompt"]


# ===== from test_marketing_graph_vision_optional.py =====
from pathlib import Path

from PIL import Image

from orchestrator.app.graph.builder import build_marketing_graph


def _image__test_marketing_graph_vision_optional(path: Path, color=(180, 120, 90)) -> Path:
    return write_test_png(path, color=color)


def _request__test_marketing_graph_vision_optional(job_id: str, **extra):
    request = make_marketing_request(
        mode="auto_pilot",
        job_id=job_id,
        context={
            "business_type": "restaurant",
            "item_or_service": "cake",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    )
    request.update(extra)
    return request


def test_marketing_graph_without_image_path_keeps_t2i_only_route():
    result = build_marketing_graph().invoke(_request__test_marketing_graph_vision_optional("vision-none"), config={"configurable": {"thread_id": "vision-none"}})

    assert result["status"] == "done"
    assert result["vision_pipeline_results"] == []
    assert result["t2i_request"]["metadata"]["vision_pipeline_enabled"] is False


def test_marketing_graph_with_source_image_runs_product_preprocess_to_result(tmp_path):
    source = _image__test_marketing_graph_vision_optional(tmp_path / "source.png")

    result = build_marketing_graph().invoke(
        _request__test_marketing_graph_vision_optional("vision-source", source_image_path=str(source)),
        config={"configurable": {"thread_id": "vision-source"}},
    )

    metadata = result["t2i_request"]["metadata"]
    assert result["status"] == "done"
    assert result["product_preserve_spec"]["preserve_strategy"] == "center_bbox_stub"
    assert result["current_brief"]["product_preserve_ready"] is True
    assert metadata["vision_pipeline_enabled"] is True
    assert metadata["source_image_path"] == str(source)
    assert result["t2i_request"]["input_image_paths"] == [str(source)]
    assert metadata["product_preserve_spec"]["metadata"]["sam_used"] is False
    assert result["result_payload"]["output_path"]


def test_marketing_graph_with_reference_image_runs_reference_preprocess_to_result(tmp_path):
    reference = _image__test_marketing_graph_vision_optional(tmp_path / "reference.png", color=(240, 120, 160))

    result = build_marketing_graph().invoke(
        _request__test_marketing_graph_vision_optional("vision-reference", reference_image_path=str(reference)),
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
    source = _image__test_marketing_graph_vision_optional(tmp_path / "source-no-copy.png")
    request = _request__test_marketing_graph_vision_optional("vision-no-copy", source_image_path=str(source), copy_generation_mode="no_copy")

    result = build_marketing_graph().invoke(request, config={"configurable": {"thread_id": "vision-no-copy"}})

    assert result["status"] == "done"
    assert result["copy_spec"]["copy_mode"] == "no_copy"
    assert result["render_result"] is None
    assert result["result_payload"]["has_text_overlay"] is False
    assert result["t2i_request"]["metadata"]["render_text_in_image"] is False
