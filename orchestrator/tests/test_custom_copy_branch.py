from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.custom_copy import custom_copy_validation_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(headline=None, subcopy=None):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="custom_input",
            user_custom_headline=headline,
            user_custom_subcopy=subcopy,
            context=MarketingContext(business_type="cafe", item_or_service="딸기 케이크", promotion_goal="new_launch", extra={"ad_format": "instagram_feed"}),
        )
    )


def test_custom_copy_validation_uses_user_text_without_rewriting():
    state = _state("봄처럼 달콤한 딸기 케이크를 오늘만 특별하게", "이번 주 한정 메뉴")
    update = custom_copy_validation_node(state)

    assert update["marketing_copy"]["headline"] == "봄처럼 달콤한 딸기 케이크를 오늘만 특별하게"
    assert update["marketing_copy"]["subcopy"] == "이번 주 한정 메뉴"
    assert update["marketing_copy"]["metadata"]["warnings"]


def test_custom_copy_validation_allows_missing_subcopy():
    update = custom_copy_validation_node(_state("딸기 케이크 출시"))

    assert update["marketing_copy"]["headline"] == "딸기 케이크 출시"
    assert update["marketing_copy"]["subcopy"] is None
