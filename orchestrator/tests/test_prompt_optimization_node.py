from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.prompt_optimization import prompt_optimization_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="삼겹살",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    state["marketing_copy"] = {
        "headline": "오늘 회식은 삼겹살로 결정",
        "subcopy": "두툼하게 준비한 삼겹살과 편안한 자리",
        "cta": "예약 문의하기",
    }
    return state


def test_prompt_optimization_fills_image_prompt_core_fields():
    update = prompt_optimization_node(_state())
    prompt = update["image_prompt"]

    for field in ["subject", "style", "lighting", "composition", "copy_space", "negative_prompt"]:
        assert prompt[field]


def test_prompt_optimization_negative_prompt_blocks_text_artifacts():
    negative = prompt_optimization_node(_state())["image_prompt"]["negative_prompt"]

    for phrase in ["text", "watermark", "logo", "letters", "numbers"]:
        assert phrase in negative


def test_prompt_optimization_user_guide_is_korean_summary():
    guide = prompt_optimization_node(_state())["user_readable_image_guide"]

    assert "텍스트 없는 배경" in guide["summary"]
    assert guide["copy_space"] == "bottom"
    assert guide["warnings"]
