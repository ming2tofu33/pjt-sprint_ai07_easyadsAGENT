from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyTagRequirement,
)


def _profile(**overrides) -> VisualStrategyProfile:
    data = {
        "strategy_id": "strategy_alpha",
        "archetype": "product_hero",
        "supported_domains": [CanonicalBusinessDomain.RETAIL],
        "composition_template_id": "template_alpha",
        "mood_preset_id": "preset_alpha",
        "copy_tone_profile_id": "tone_alpha",
        "priority": 10,
        "enabled": True,
    }
    data.update(overrides)
    return VisualStrategyProfile(**data)


def test_visual_strategy_profile_fields_are_exact_contract():
    assert set(VisualStrategyProfile.model_fields) == {
        "strategy_id",
        "archetype",
        "supported_domains",
        "supported_campaign_roles",
        "supported_placements",
        "required_tags",
        "preferred_tags",
        "excluded_tags",
        "required_tag_requirements",
        "introduced_visual_elements",
        "visual_element_evidence_requirements",
        "composition_template_id",
        "mood_preset_id",
        "copy_tone_profile_id",
        "provider_capabilities",
        "priority",
        "fallback_tier",
        "enabled",
    }


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("strategy_id", ""),
        ("archetype", " "),
        ("composition_template_id", 123),
        ("mood_preset_id", True),
        ("copy_tone_profile_id", object()),
    ],
)
def test_required_labels_are_strict_non_empty_strings(field_name: str, value):
    with pytest.raises(ValidationError):
        _profile(**{field_name: value})


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("supported_campaign_roles", ["seasonal", 123]),
        ("supported_placements", [{"unexpected": "value"}]),
        ("required_tags", ["valid", True]),
        ("preferred_tags", [object()]),
        ("excluded_tags", [1.2]),
        ("provider_capabilities", ["valid", 123]),
    ],
)
def test_open_vocabulary_sets_reject_non_string_items(field_name: str, value):
    with pytest.raises(ValidationError):
        _profile(**{field_name: value})


def test_open_vocabulary_sets_trim_drop_empty_and_deduplicate_without_aliasing():
    profile = _profile(required_tags=[" Alpha ", "Alpha", "", "alpha"])

    assert profile.required_tags == frozenset({"Alpha", "alpha"})


def test_supported_domains_require_canonical_domain_values():
    assert _profile(supported_domains=[CanonicalBusinessDomain.BEAUTY]).supported_domains == frozenset({CanonicalBusinessDomain.BEAUTY})
    assert _profile(supported_domains=["beauty"]).supported_domains == frozenset({CanonicalBusinessDomain.BEAUTY})

    for value in ([], ["cafe"], ["food"], None):
        with pytest.raises(ValidationError):
            _profile(supported_domains=value)


def test_priority_and_enabled_are_strict():
    with pytest.raises(ValidationError):
        _profile(priority=-1)
    for value in ("10", 1.5, True, None):
        with pytest.raises(ValidationError):
            _profile(priority=value)
    for value in ("true", 1, None):
        with pytest.raises(ValidationError):
            _profile(enabled=value)


@pytest.mark.parametrize(
    "field_name",
    ["required_tags", "preferred_tags"],
)
def test_positive_tags_cannot_overlap_excluded_tags(field_name: str):
    with pytest.raises(ValidationError):
        _profile(**{field_name: ["shared"], "excluded_tags": ["shared"]})


def test_required_and_preferred_tags_cannot_overlap():
    with pytest.raises(ValidationError):
        _profile(required_tags=["shared"], preferred_tags=["shared"])


def test_json_round_trip_and_collection_immutability():
    profile = _profile(
        required_tag_requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.BUSINESS,
                all_of=["business_signal_alpha"],
            ),
        )
    )
    restored = VisualStrategyProfile.model_validate_json(profile.model_dump_json())

    assert restored == profile
    with pytest.raises(ValidationError):
        profile.priority = 0
    with pytest.raises(AttributeError):
        profile.required_tags.add("new_tag")


def test_tag_requirement_accepts_source_scoped_open_vocabulary_tags():
    requirement = VisualStrategyTagRequirement(
        source=VisualStrategyContextSource.PRODUCT_VISUAL,
        all_of=[" product_signal_beta "],
        any_of=["semantic_signal_gamma"],
    )

    assert requirement.source == VisualStrategyContextSource.PRODUCT_VISUAL
    assert requirement.all_of == frozenset({"product_signal_beta"})
    assert requirement.any_of == frozenset({"semantic_signal_gamma"})


def test_tag_requirement_rejects_empty_or_conflicting_conditions():
    with pytest.raises(ValidationError):
        VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS)
    with pytest.raises(ValidationError):
        VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["same"], any_of=["same"])
    with pytest.raises(ValidationError):
        VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=[123])


def test_context_source_is_not_routing_evidence_source():
    assert VisualStrategyContextSource.BUSINESS.value == "business"
    assert VisualStrategyContextSource.PRODUCT_VISUAL.value == "product_visual"


def test_visual_element_evidence_requirement_contract():
    requirement = VisualElementEvidenceRequirement(
        element=" visual_element_alpha ",
        requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.PRODUCT_VISUAL,
                all_of=["product_signal_beta"],
            ),
        ),
    )

    assert requirement.element == "visual_element_alpha"
    with pytest.raises(ValidationError):
        VisualElementEvidenceRequirement(element="", requirements=(requirement.requirements[0],))
    with pytest.raises(ValidationError):
        VisualElementEvidenceRequirement(element="visual_element_alpha", requirements=())


def test_profile_visual_element_requirements_must_reference_introduced_elements():
    req = VisualElementEvidenceRequirement(
        element="visual_element_alpha",
        requirements=(VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL, all_of=["product_signal_beta"]),),
    )

    assert _profile(introduced_visual_elements=["visual_element_alpha"], visual_element_evidence_requirements=(req,)).introduced_visual_elements == frozenset({"visual_element_alpha"})
    with pytest.raises(ValidationError):
        _profile(visual_element_evidence_requirements=(req,))
    with pytest.raises(ValidationError):
        _profile(introduced_visual_elements=["visual_element_alpha"], visual_element_evidence_requirements=(req, req))


def test_fallback_tier_is_strict_non_negative_integer():
    assert _profile(fallback_tier=1).fallback_tier == 1
    for value in (-1, "1", 1.5, True, None):
        with pytest.raises(ValidationError):
            _profile(fallback_tier=value)
