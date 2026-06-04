from typing import get_args

from orchestrator.app.llm.option_registry import OPTION_QUESTION_REGISTRY, get_next_missing_field, get_option_question
from orchestrator.app.schemas.llm_marketing import MissingField


def test_option_question_fields_are_missing_fields():
    missing_fields = set(get_args(MissingField))

    for field, question in OPTION_QUESTION_REGISTRY.items():
        assert field in missing_fields
        assert question.field in missing_fields


def test_option_item_ids_are_unique_per_question():
    for question in OPTION_QUESTION_REGISTRY.values():
        ids = [item.id for item in question.options]
        assert len(ids) == len(set(ids)), question.field


def test_dessert_is_not_mapped_to_beauty_salon():
    business_question = get_option_question("business_type")
    dessert_values = [item.value for item in business_question.options if "디저트" in item.label]

    assert dessert_values
    assert "beauty_salon" not in dessert_values


def test_ad_format_has_flyer_and_no_a4_value():
    ad_format_question = get_option_question("ad_format")
    values = [item.value for item in ad_format_question.options]

    assert "flyer" in values
    assert "A4" not in values


def test_engine_and_copy_space_questions_are_not_in_registry():
    assert "generation_engine" not in OPTION_QUESTION_REGISTRY
    assert "engine" not in OPTION_QUESTION_REGISTRY
    assert "copy_space" not in OPTION_QUESTION_REGISTRY


def test_usp_question_is_multi_select():
    assert get_option_question("usp").multi_select is True


def test_next_missing_field_uses_priority_order():
    assert get_next_missing_field(["brand_tone", "ad_format", "usp"]) == "ad_format"
    assert get_next_missing_field(["custom_request", "region_type"]) == "region_type"
    assert get_next_missing_field(["platform", "aspect_ratio"]) is None
