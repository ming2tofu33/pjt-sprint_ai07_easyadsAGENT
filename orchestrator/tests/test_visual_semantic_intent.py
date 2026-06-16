from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent


def _intent(**overrides) -> VisualSemanticIntent:
    data = {
        "subject_priority": 0.8,
        "environment_priority": 0.7,
        "text_priority": 0.6,
        "copy_presence_mode": "open_copy_mode",
        "confidence": 0.9,
    }
    data.update(overrides)
    return VisualSemanticIntent(**data)


def test_visual_semantic_intent_fields_are_exact_contract():
    assert set(VisualSemanticIntent.model_fields) == {
        "subject_priority",
        "environment_priority",
        "text_priority",
        "desired_moods",
        "desired_materials",
        "lighting_preferences",
        "composition_preferences",
        "required_visual_facts",
        "prohibited_visual_elements",
        "copy_presence_mode",
        "confidence",
    }


@pytest.mark.parametrize("extra_field", ["preset_id", "template_id", "strategy_id", "provider", "engine", "registry_id"])
def test_extra_internal_fields_are_rejected(extra_field: str):
    with pytest.raises(ValidationError):
        _intent(**{extra_field: "not_allowed"})


def test_priority_bounds_and_sum_not_normalized():
    intent = _intent(subject_priority=1.0, environment_priority=1.0, text_priority=1.0, confidence=0.0)

    assert intent.subject_priority + intent.environment_priority + intent.text_priority == 3.0
    for field in ("subject_priority", "environment_priority", "text_priority", "confidence"):
        with pytest.raises(ValidationError):
            _intent(**{field: -0.01})
        with pytest.raises(ValidationError):
            _intent(**{field: 1.01})


def test_copy_presence_mode_is_required_open_nonempty_string():
    assert _intent(copy_presence_mode=" custom_mode ").copy_presence_mode == "custom_mode"
    for value in ("", " ", 1, True, None):
        with pytest.raises(ValidationError):
            _intent(copy_presence_mode=value)


@pytest.mark.parametrize(
    "field_name",
    [
        "desired_moods",
        "desired_materials",
        "lighting_preferences",
        "composition_preferences",
        "required_visual_facts",
        "prohibited_visual_elements",
    ],
)
def test_open_vocabulary_lists_normalize_without_aliasing(field_name: str):
    intent = _intent(**{field_name: [" TokenA ", "TokenA", "", "tokena"]})

    assert getattr(intent, field_name) == ("TokenA", "tokena")


def test_open_vocabulary_lists_reject_non_strings():
    with pytest.raises(ValidationError):
        _intent(desired_moods=["valid", 1])


def test_required_prohibited_conflict_is_casefold_exact_only():
    with pytest.raises(ValidationError):
        _intent(required_visual_facts=["Smoke"], prohibited_visual_elements=["smoke"])

    intent = _intent(required_visual_facts=["grilled"], prohibited_visual_elements=["grill"])
    assert intent.required_visual_facts == ("grilled",)


def test_json_round_trip_and_frozen_attribute():
    intent = _intent(desired_moods=["novel_semantic_token_572"])
    restored = VisualSemanticIntent.model_validate_json(intent.model_dump_json())

    assert restored == intent
    with pytest.raises(ValidationError):
        intent.confidence = 0.1
    with pytest.raises(AttributeError):
        intent.desired_moods.append("extra")
