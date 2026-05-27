from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(brand_tone=None, promotion_goal="reservation_cta"):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal=promotion_goal,
                brand_tone=brand_tone,
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )


def test_text_style_binder_maps_tone_profiles():
    assert text_style_binder_node(_state("premium"))["text_style_spec"]["profile"] == "premium"
    assert text_style_binder_node(_state("귀여운"))["text_style_spec"]["profile"] == "cute"
    assert text_style_binder_node(_state(None, "discount_event"))["text_style_spec"]["profile"] == "event"
    assert text_style_binder_node(_state())["text_style_spec"]["profile"] == "emotional"
