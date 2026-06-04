import re

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copywriting import copywriting_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(**context_overrides):
    context = {
        "business_type": "restaurant",
        "item_or_service": "삼겹살",
        "promotion_goal": "reservation_cta",
        "extra": {"ad_format": "instagram_feed"},
    }
    context.update(context_overrides)
    return create_initial_marketing_state(
        InitialMarketingRequest(user_input="ready", context=MarketingContext(**context))
    )


def test_copywriting_node_creates_marketing_copy():
    update = copywriting_node(_state())

    assert update["marketing_copy"]["headline"]
    assert update["marketing_copy"]["subcopy"]
    assert update["marketing_copy"]["cta"] == "예약 문의하기"


def test_copywriting_does_not_hallucinate_phone_address_discount_or_date():
    copy = copywriting_node(_state())["marketing_copy"]
    rendered = " ".join(str(value or "") for value in copy.values())

    assert not re.search(r"\d{2,3}-\d{3,4}-\d{4}", rendered)
    assert "주소" not in rendered
    assert "%" not in rendered
    assert "2026" not in rendered


def test_copywriting_uses_price_and_contact_only_when_provided():
    update = copywriting_node(_state(price_or_discount="2인 세트 29,000원", contact_or_order_method="네이버 예약"))

    assert update["marketing_copy"]["price_line"] == "2인 세트 29,000원"
    assert update["marketing_copy"]["cta"] == "네이버 예약로 문의하기"
