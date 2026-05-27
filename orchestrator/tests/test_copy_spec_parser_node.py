from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_copy_spec_parser_maps_marketing_copy_roles_without_new_claims():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state["marketing_copy"] = {
        "headline": "오늘 회식은 삼겹살로 결정",
        "subcopy": "두툼하게 준비한 삼겹살과 편안한 자리",
        "cta": "예약 문의하기",
        "hashtags": ["#삼겹살"],
        "metadata": {},
    }

    update = copy_spec_parser_node(state)
    items = update["copy_spec"]["items"]
    rendered = " ".join(item["text"] for item in items)

    assert [item["role"] for item in items] == ["headline", "subheadline", "cta"]
    assert "010-" not in rendered
    assert "주소" not in rendered
    assert "%" not in rendered
