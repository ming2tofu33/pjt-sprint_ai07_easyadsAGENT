from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.tone_binding import build_tone_binding_prompt, tone_binding_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_tone_binding_returns_profile_for_restaurant_feed():
    state = create_state()

    update = tone_binding_node(state)
    output = update["tone_binding_output"]

    assert output["tone_profile"]
    assert output["forbidden_claims"]
    assert output["channel_copy_rules"]
    assert output["metadata"]["source_node"] == "tone_binding"
    assert output["metadata"]["llm_metadata"]["fallback_used"] is True
    assert output["metadata"]["llm_metadata"]["node_name"] == "tone_binding"
    assert "tone_binding_ready" in update["current_brief"]
    assert update["model_selections"][0]["node_name"] == "tone_binding"
    assert update["llm_call_results"][0]["node_name"] == "tone_binding"


def test_tone_binding_prompt_uses_metadata_contract():
    state = create_state()

    prompt = build_tone_binding_prompt(state)

    assert "metadata_contract=" in prompt
    assert "ToneBindingOutput" in prompt
    assert "Do not invent phone numbers" in prompt
    assert "render_text_in_image" in prompt


def create_state():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    return state
