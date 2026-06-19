from typing import get_type_hints

from orchestrator.app.graph.state import MarketingState, create_initial_marketing_state, engine_for_render_profile
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest
from orchestrator.app.graph.routers import should_use_native_typography_lane


def test_marketing_state_exposes_required_boundary_keys():
    hints = get_type_hints(MarketingState, include_extras=True)
    assert {
        "context",
        "current_brief",
        "input_evidence_bundle",
        "product_understanding",
        "copy_spec",
        "text_layout_spec",
        "text_style_spec",
        "image_prompt_spec",
        "t2i_request",
        "result_payload",
        "source_asset_id",
        "reference_asset_id",
    } <= set(hints)


def test_marketing_state_uses_canonical_default_engines():
    assert engine_for_render_profile("premium_api") == "gpt_image_2"
    assert engine_for_render_profile("premium_local") == "flux2_klein_4b"
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="Create an ad", render_profile="premium_api"))
    assert state["engine"] == "gpt_image_2"


def test_source_asset_keeps_gpt_image_2_on_input_aware_t2i_lane():
    assert should_use_native_typography_lane(
        {"engine": "gpt_image_2", "selected_ad_format": "instagram_feed", "source_asset_id": "asset_source"}
    ) is False
