import json

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node, state_update_selected_copy_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state():
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )


def test_copy_candidate_generation_is_stable_and_safe():
    update = copy_candidate_generation_node(_state())
    candidates = update["copy_candidates"]
    rendered = " ".join(str(value) for candidate in candidates for value in candidate.values())

    assert [candidate["id"] for candidate in candidates] == ["copy_1", "copy_2"]
    assert "010-" not in rendered
    assert "주소" not in rendered
    assert "%" not in rendered
    json.dumps({"candidates": candidates}, ensure_ascii=False)


def test_selected_copy_updates_marketing_copy_and_copy_spec():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = {"selected_copy_id": "copy_2"}
    state.update(state_update_selected_copy_node(state))
    state.update(copy_spec_parser_node(state))

    assert state["selected_copy_id"] == "copy_2"
    assert state["marketing_copy"]["headline"] == "회식은 역시 삼겹살"
    assert state["copy_spec"]["items"][0]["role"] == "headline"
