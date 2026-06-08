from orchestrator.app.graph.nodes import validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _validated_state(text: str):
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=text))
    update = validator_node(state)
    state.update(update)
    return state


def test_validator_infers_samgyeopsal_instagram_context():
    state = _validated_state("우리 삼겹살집 인스타 광고")

    assert state["context"]["business_type"] == "restaurant"
    assert state["context"]["item_or_service"] == "삼겹살"
    assert state["context"]["extra"]["ad_format"] == "instagram_feed"
    assert "promotion_goal" in state["missing_fields"]


def test_validator_infers_raw_meat_sale_feed_context():
    state = _validated_state("고기집 원육 세일 피드 스타일로 고기99 음식점 광고를 만들어줘")

    assert state["context"]["business_type"] == "restaurant"
    assert state["context"]["item_or_service"] == "원육"
    assert state["context"]["promotion_goal"] == "discount_event"
    assert state["context"]["extra"]["ad_format"] == "instagram_feed"
    assert "business_type" not in state["missing_fields"]
    assert "item_or_service" not in state["missing_fields"]
    assert "promotion_goal" not in state["missing_fields"]
    assert "ad_format" not in state["missing_fields"]


def test_validator_infers_nail_summer_story_context():
    state = _validated_state("네일샵 여름 이벤트 인스타 스토리 만들어줘")

    assert state["context"]["business_type"] == "beauty_nail"
    assert state["context"]["item_or_service"] == "네일 서비스"
    assert state["context"]["promotion_goal"] == "seasonal_limited"
    assert state["context"]["extra"]["ad_format"] == "instagram_story"
    assert "business_type" not in state["missing_fields"]
    assert "item_or_service" not in state["missing_fields"]
    assert "promotion_goal" not in state["missing_fields"]
    assert "ad_format" not in state["missing_fields"]


def test_validator_creates_missing_fields_when_input_is_sparse():
    state = _validated_state("광고 만들어줘")

    assert set(["business_type", "item_or_service", "promotion_goal", "ad_format"]).issubset(state["missing_fields"])
    assert state["validator_output"]["needs_user_selection"] is True


def test_validator_marks_ready_for_planning_when_required_fields_exist():
    request = InitialMarketingRequest(
        user_input="삼겹살 할인 인스타 광고",
        copy_generation_mode="auto_pilot",
        context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="discount_event", extra={"ad_format": "instagram_feed"}),
    )
    state = create_initial_marketing_state(request)
    state.update(validator_node(state))

    assert state["missing_fields"] == []
    assert state["current_brief"]["ready_for_planning"] is True
