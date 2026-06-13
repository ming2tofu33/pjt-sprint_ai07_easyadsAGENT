from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def make_copy_state(
    *,
    business_type: str = "restaurant",
    item_or_service: str = "삼겹살",
    promotion_goal: str = "reservation_cta",
    copy_generation_mode: str = "suggest_candidates",
):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode=copy_generation_mode,
            context=MarketingContext(
                business_type=business_type,
                item_or_service=item_or_service,
                promotion_goal=promotion_goal,
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
