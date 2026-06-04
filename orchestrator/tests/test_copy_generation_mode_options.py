from orchestrator.app.llm.option_registry import OPTION_QUESTION_REGISTRY


def test_copy_generation_mode_option_question_exists_with_dependencies():
    question = OPTION_QUESTION_REGISTRY["copy_generation_mode"]
    values = {option.value for option in question.options}

    assert values == {"suggest_candidates", "auto_pilot", "no_copy", "custom_input"}
    dependency = question.metadata["dependency_fields"]
    assert dependency["if_value_equals"] == "custom_input"
    fields = {item["field"] for item in dependency["show_sub_fields"]}
    assert {"user_custom_headline", "user_custom_subcopy"} <= fields


def test_engine_and_copy_space_questions_are_not_reintroduced():
    assert "generation_engine" not in OPTION_QUESTION_REGISTRY
    assert "copy_space" not in OPTION_QUESTION_REGISTRY
