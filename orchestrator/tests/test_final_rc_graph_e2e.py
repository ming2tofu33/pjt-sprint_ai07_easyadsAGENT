from pathlib import Path

from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.nodes import infer_ad_format
from orchestrator.app.graph.routers import route_by_copy_presence
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _final_rc_request(job_id: str, render_options: dict | None = None) -> dict:
    request = {
        "user_input": "망고 빙수 여름 카페 광고",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": "auto_pilot",
        "renderer_mode": "poster_components",
        "render_profile": "fast",
        "context": {
            "business_type": "cafe",
            "item_or_service": "망고 빙수",
            "promotion_goal": "seasonal_menu",
            "brand_tone": "fresh and clean",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    if render_options is not None:
        request["render_options"] = render_options
    return request


def _invoke(request: dict) -> dict:
    return build_marketing_graph().invoke(
        request,
        config={"configurable": {"thread_id": request["thread_id"]}},
    )


def _render_metadata(result: dict) -> dict:
    return (result.get("render_result") or {}).get("metadata") or {}


def test_final_rc_graph_runs_poster_components_through_quality_and_recommendation():
    result = _invoke(_final_rc_request("final-rc-graph-e2e"))
    metadata = _render_metadata(result)
    result_payload_metadata = (result.get("result_payload") or {}).get("metadata") or {}
    passthrough_metadata = result_payload_metadata.get("render_metadata") or {}

    assert result["status"] == "done"
    assert result["renderer_mode"] == "poster_components"
    assert result["final_image_path"].endswith("final_composite_poster.png")
    assert Path(result["final_image_path"]).exists()
    assert result["poster_layout_spec"]
    assert result["image_analysis"]

    for key in [
        "planner_diagnostics",
        "template_diagnostics",
        "asset_diagnostics",
        "component_diagnostics",
        "image_aware_quality_diagnostics",
        "design_recommendation",
    ]:
        assert metadata.get(key), f"missing render_result.metadata.{key}"
        assert passthrough_metadata.get(key), f"missing result_payload.metadata.render_metadata.{key}"

    assert metadata["render_success"] is True
    assert metadata["quality_pass"] is True
    assert metadata["layout_quality_pass"] is True
    assert metadata["image_aware_quality_diagnostics"].get("image_aware_quality_pass") is True
    assert metadata["design_recommendation"].get("recommendation_level")


def test_final_rc_graph_preserves_palette_diagnostics_when_render_options_enabled():
    result = _invoke(
        _final_rc_request(
            "final-rc-graph-e2e-palette",
            render_options={
                "enable_palette_enhancement": True,
                "enable_local_contrast_text": True,
            },
        )
    )
    metadata = _render_metadata(result)
    passthrough_metadata = ((result.get("result_payload") or {}).get("metadata") or {}).get("render_metadata") or {}

    assert result["status"] == "done"
    assert metadata.get("palette_diagnostics")
    assert metadata.get("component_color_decisions")
    assert passthrough_metadata.get("palette_diagnostics")
    assert passthrough_metadata.get("component_color_decisions")


def _planned_state_for_ad_format(ad_format: str | None, *, renderer_mode: str | None = None) -> dict:
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="카페 광고 만들어줘",
            requested_ad_format=ad_format,
            renderer_mode=renderer_mode,
            context={
                "business_type": "cafe",
                "item_or_service": "망고 빙수",
                "promotion_goal": "seasonal_menu",
            },
        )
    )
    state.update(format_planner_node(state))
    return state


def test_ad_format_poster_sets_poster_renderer_mode_before_copy_router():
    state = _planned_state_for_ad_format("poster")

    assert state["ad_format_spec"]["ad_format"] == "poster"
    assert state["renderer_mode"] == "poster_components"
    assert route_by_copy_presence(state) == "image_analysis"


def test_non_poster_ad_format_keeps_simple_text_copy_router_path():
    state = _planned_state_for_ad_format("instagram_feed")

    assert state["ad_format_spec"]["ad_format"] == "instagram_feed"
    assert state.get("renderer_mode") is None
    assert route_by_copy_presence(state) == "text_renderer"


def test_explicit_renderer_mode_is_not_overwritten_by_poster_ad_format():
    state = _planned_state_for_ad_format("poster", renderer_mode="simple_text")

    assert state["ad_format_spec"]["ad_format"] == "poster"
    assert state["renderer_mode"] == "simple_text"
    assert route_by_copy_presence(state) == "text_renderer"


def test_reference_template_poster_ad_format_sets_poster_renderer_mode():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="이 레퍼런스처럼 만들어줘",
            context={
                "business_type": "cafe",
                "item_or_service": "망고 빙수",
                "promotion_goal": "seasonal_menu",
            },
        )
    )
    state["selected_reference_template"] = {"template_id": "ref_poster", "ad_formats": ["poster"]}

    state.update(format_planner_node(state))

    assert state["ad_format_spec"]["ad_format"] == "poster"
    assert state["renderer_mode"] == "poster_components"
    assert route_by_copy_presence(state) == "image_analysis"


def test_korean_poster_keyword_infers_poster_ad_format():
    assert infer_ad_format("망고 빙수 포스터 만들어줘") == "poster"
