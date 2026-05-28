from orchestrator.app.llm.plan_policy import build_default_plan_policy, get_default_node_policies, normalize_user_plan


def test_normalize_user_plan_defaults_to_free():
    assert normalize_user_plan(None) == "free"
    assert normalize_user_plan("unknown") == "free"
    assert normalize_user_plan("premium") == "premium"


def test_default_plan_policy_by_plan():
    free = build_default_plan_policy("free")
    economic = build_default_plan_policy("economic")
    premium = build_default_plan_policy("premium")
    benchmark = build_default_plan_policy("internal_benchmark")

    assert not any(model.startswith("api_") for model in free.allowed_model_classes)
    assert free.max_api_calls_per_job == 0
    assert {"api_nano", "api_mini"} <= set(economic.allowed_model_classes)
    assert "api_full" not in economic.allowed_model_classes
    assert "api_vision" not in economic.allowed_model_classes
    assert {"api_full", "api_vision"} <= set(premium.allowed_model_classes)
    assert set(benchmark.allowed_model_classes) == {"local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"}


def test_default_node_policies_include_llm_nodes():
    policies = get_default_node_policies("premium")

    for node_name in [
        "validator",
        "copy_mode_inference",
        "tone_binding",
        "copy_candidate_generation",
        "auto_pilot_copywriting",
        "custom_copy_validation",
        "copy_spec_parser",
        "image_prompt_planner",
        "background_validation",
        "final_validation",
        "revision_intent_classifier",
    ]:
        assert node_name in policies
        assert policies[node_name].requires_structured_output is True
