from orchestrator.app.graph.nodes import infer_copy_generation_mode, validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_copy_mode_heuristics():
    assert infer_copy_generation_mode("카피 없이 이미지만") == "no_copy"
    assert infer_copy_generation_mode("문구는 내가 넣을게") == "custom_input"
    assert infer_copy_generation_mode("알아서 문구까지 만들어줘") == "auto_pilot"
    assert infer_copy_generation_mode("카피 여러 개 추천해줘") == "suggest_candidates"


def test_unknown_copy_mode_remains_missing():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(validator_node(state))

    assert "copy_generation_mode" in state["missing_fields"]


def test_initial_request_copy_mode_beats_heuristic():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="카피 없이 이미지만",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(validator_node(state))

    assert state["copy_generation_mode"] == "auto_pilot"
    assert "copy_generation_mode" not in state["missing_fields"]
