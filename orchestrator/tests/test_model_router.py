from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.plan_policy import build_default_plan_policy


def test_free_plan_never_selects_api_class():
    selection = choose_model("image_prompt_planner", "free", confidence=0.2, risk_level="high", vision_required=True)

    assert not selection.selected_model_class.startswith("api_")
    assert selection.estimated_cost_tier == "none"
    assert selection.reason


def test_economic_low_confidence_can_escalate_without_full_or_vision():
    selection = choose_model("auto_pilot_copywriting", "economic", confidence=0.4, risk_level="high")

    assert selection.selected_model_class in {"api_nano", "api_mini", "local_quality", "local_fast", "mock"}
    assert selection.selected_model_class not in {"api_full", "api_vision"}
    assert selection.provider in {"openai", "local_gemma", "mock"}


def test_premium_generation_and_vision_selection():
    prompt_selection = choose_model("image_prompt_planner", "premium", latency_budget="standard")
    vision_selection = choose_model("background_validation", "premium", vision_required=True)

    assert prompt_selection.selected_model_class in {"api_full", "api_mini"}
    assert prompt_selection.provider == "openai"
    assert vision_selection.selected_model_class == "api_vision"
    assert vision_selection.provider == "vision_api"


def test_unknown_node_safe_fallback_does_not_crash():
    selection = choose_model("unknown_node", "premium")

    assert selection.fallback_used is True
    assert selection.reason
    assert selection.selected_model_class in build_default_plan_policy("premium").allowed_model_classes


def test_plan_policy_dict_is_supported():
    policy = build_default_plan_policy("free").model_dump()
    selection = choose_model("validator", "free", plan_policy=policy)

    assert selection.user_plan == "free"
    assert selection.selected_model_class in {"local_fast", "local_quality", "mock"}
