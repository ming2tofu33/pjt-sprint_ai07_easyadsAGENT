from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.reference_catalog.nodes import reference_template_resolve_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_reference_template_resolve_node_stores_template_and_artifact():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            selected_reference_template_id="seed_cafe_strawberry_feed_001",
        )
    )

    update = reference_template_resolve_node(state)

    assert update["selected_reference_template"]["template_id"] == "seed_cafe_strawberry_feed_001"
    assert update["reference_template_selection"]["template_id"] == "seed_cafe_strawberry_feed_001"
    assert update["current_brief"]["reference_template_selected"] is True
    assert update["artifact_refs"][0]["artifact_type"] == "reference_template"
    assert "reference_template_warning" in update["current_brief"]


def test_reference_template_resolve_node_adds_template_context_hints():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="고기99 광고 만들어줘",
            selected_reference_template_id="ref_restaurant_3_1_018",
        )
    )

    update = reference_template_resolve_node(state)

    assert update["context"]["business_type"] == "restaurant"
    assert update["context"]["item_or_service"] == "원육"
    assert update["context"]["extra"]["ad_format"] == "instagram_feed"
    assert update["context"]["extra"]["selected_reference_template_id"] == "ref_restaurant_3_1_018"
    assert update["current_brief"]["requested_ad_format"] == "instagram_feed"


def test_reference_template_resolve_node_does_not_overwrite_explicit_context():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="카페 신메뉴 포스터 만들어줘",
            selected_reference_template_id="ref_restaurant_3_1_018",
            context=MarketingContext(
                business_type="cafe",
                item_or_service="라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "poster"},
            ),
        )
    )

    update = reference_template_resolve_node(state)

    assert update["context"]["business_type"] == "cafe"
    assert update["context"]["item_or_service"] == "라떼"
    assert update["context"]["promotion_goal"] == "new_launch"
    assert update["context"]["extra"]["ad_format"] == "poster"
    assert update["context"]["extra"]["selected_reference_template_id"] == "ref_restaurant_3_1_018"


def test_reference_template_resolve_node_invalid_id_does_not_crash():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            selected_reference_template_id="missing_template",
        )
    )

    update = reference_template_resolve_node(state)

    assert update["reference_template_selection"]["warnings"] == ["reference_template_not_found"]
    assert update["current_brief"]["reference_template_error"] == "reference_template_not_found"
    assert "missing_template" in update["error_message"]


def test_reference_template_resolve_node_no_id_is_noop():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ready"))

    assert reference_template_resolve_node(state) == {}
