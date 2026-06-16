from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.product_visual_context_service import (
    build_product_visual_context,
    product_visual_context_from_understanding,
)
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.input_evidence import EvidenceItem
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext


def _evidence(
    key: str,
    value: str,
    *,
    evidence_class: str = "verified_fact",
    source: str = "user_text",
    usable_for_copy: bool = True,
    confidence: float = 0.9,
) -> EvidenceItem:
    return EvidenceItem(
        key=key,
        value=value,
        source=source,
        evidence_class=evidence_class,
        confidence=confidence,
        usable_for_copy=usable_for_copy,
    )


def _understanding() -> ProductUnderstanding:
    name = _evidence("product_name", "desk lamp")
    visual = _evidence(
        "visible_attribute",
        "brass_finish",
        evidence_class="visual_observation",
        source="image_vlm",
    )
    inference = _evidence(
        "visual_inference",
        "warm_light",
        evidence_class="creative_inference",
        usable_for_copy=False,
        confidence=0.6,
    )
    return ProductUnderstanding(
        product_name="desk lamp",
        normalized_product_type="desk_lamp",
        product_variant="adjustable_arm",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting", "desk_lamp"],
        product_form="table_lamp",
        use_contexts=["home_office"],
        verified_facts=[name],
        visual_observations=[visual],
        permissible_inferences=[inference],
        product_name_evidence_ids=[name.evidence_id],
        confidence=0.88,
    )


def test_schema_fields_are_exact_boundary_contract():
    assert set(ProductVisualContext.model_fields) == {
        "product_name",
        "category_path",
        "product_tags",
        "visible_attributes",
        "explicit_preparation_methods",
        "permissible_visual_inferences",
        "prohibited_visual_inferences",
        "evidence_refs",
        "confidence",
    }


def test_schema_requires_product_name_and_evidence_refs():
    with pytest.raises(ValidationError):
        ProductVisualContext(evidence_refs=["test:source"], confidence=0.8)
    with pytest.raises(ValidationError):
        build_product_visual_context(product_name=" ", evidence_refs=["test:source"], confidence=0.8)
    with pytest.raises(ValidationError):
        build_product_visual_context(product_name="Product", evidence_refs=[], confidence=0.8)
    with pytest.raises(ValidationError):
        build_product_visual_context(product_name="Product", evidence_refs=[" "], confidence=0.8)


def test_confidence_bounds_json_round_trip_and_frozen_attribute():
    low = build_product_visual_context(product_name="Product", evidence_refs=["test:source"], confidence=0.0)
    high = build_product_visual_context(product_name="Product", evidence_refs=["test:source"], confidence=1.0)

    assert ProductVisualContext.model_validate_json(high.model_dump_json()) == high
    assert low.confidence == 0.0
    with pytest.raises(ValidationError):
        high.confidence = 0.5
    for confidence in (-0.01, 1.01):
        with pytest.raises(ValidationError):
            build_product_visual_context(product_name="Product", evidence_refs=["test:source"], confidence=confidence)


def test_tuple_fields_are_deeply_immutable():
    context = build_product_visual_context(
        product_name="Product",
        category_path=["category"],
        product_tags=["tag"],
        visible_attributes=["attribute"],
        evidence_refs=["test:source"],
        confidence=0.8,
    )

    with pytest.raises(AttributeError):
        context.category_path.append("other")
    with pytest.raises(AttributeError):
        context.product_tags.append("other")
    with pytest.raises(AttributeError):
        context.visible_attributes.append("other")


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("product_name", 123),
        ("category_path", ["valid", 123]),
        ("product_tags", [True]),
        ("visible_attributes", [{"unexpected": "value"}]),
        ("evidence_refs", [object()]),
    ],
)
def test_non_string_values_are_rejected(field_name: str, value: object):
    kwargs = {
        "product_name": "Product",
        "evidence_refs": ["test:source"],
        "confidence": 0.8,
        field_name: value,
    }
    with pytest.raises(ValidationError):
        ProductVisualContext(**kwargs)


def test_normalization_preserves_order_and_category_structure():
    context = build_product_visual_context(
        product_name="  향수 ",
        category_path=[" fragrance ", "", "fragrance"],
        product_tags=["premium", " premium ", "", "gift"],
        visible_attributes=["glass_bottle", "glass_bottle", "amber_liquid"],
        evidence_refs=["test:source", " test:source ", "", "catalog:item"],
        confidence=0.8,
    )

    assert context.product_name == "향수"
    assert context.category_path == ("fragrance", "fragrance")
    assert context.product_tags == ("premium", "gift")
    assert context.visible_attributes == ("glass_bottle", "amber_liquid")
    assert context.evidence_refs == ("test:source", "catalog:item")


@pytest.mark.parametrize("extra_field", ["broad_domain", "venue_type", "business_tags", "campaign_role", "preset_id", "template_id", "headline", "provider"])
def test_responsibility_boundary_rejects_extra_fields(extra_field: str):
    with pytest.raises(ValidationError):
        ProductVisualContext(
            product_name="Product",
            evidence_refs=["test:source"],
            confidence=0.8,
            **{extra_field: "not_allowed"},
        )


@pytest.mark.parametrize(
    "positive_field",
    ["product_tags", "visible_attributes", "explicit_preparation_methods", "permissible_visual_inferences"],
)
def test_exact_positive_and_prohibited_overlap_is_rejected(positive_field: str):
    with pytest.raises(ValidationError, match="visual claim cannot be both positive and prohibited"):
        ProductVisualContext(
            product_name="Product",
            evidence_refs=["test:source"],
            confidence=0.8,
            prohibited_visual_inferences=["smoke"],
            **{positive_field: ["smoke"]},
        )


def test_substring_or_semantic_similarity_is_not_conflict_checked():
    context = build_product_visual_context(
        product_name="Product",
        explicit_preparation_methods=["grilled"],
        prohibited_visual_inferences=["grill"],
        evidence_refs=["test:source"],
        confidence=0.8,
    )

    assert context.explicit_preparation_methods == ("grilled",)


def test_adapter_projects_only_explicit_product_understanding_fields():
    understanding = _understanding()

    context = product_visual_context_from_understanding(
        understanding,
        explicit_preparation_methods=["hand_assembled"],
        permissible_visual_inferences=["desk_scene"],
        prohibited_visual_inferences=["outdoor_use"],
        supplement_evidence_refs=["test:supplement"],
    )

    assert context.product_name == "desk lamp"
    assert context.category_path == ("home_and_living", "lighting", "desk_lamp")
    assert context.product_tags == ("desk_lamp", "adjustable_arm", "table_lamp")
    assert "home_office" not in context.product_tags
    assert context.visible_attributes == ("brass_finish",)
    assert context.explicit_preparation_methods == ("hand_assembled",)
    assert context.permissible_visual_inferences == ("warm_light", "desk_scene")
    assert context.prohibited_visual_inferences == ("outdoor_use",)
    assert context.confidence == 0.88
    assert "test:supplement" in context.evidence_refs


def test_adapter_rejects_ungrounded_explicit_supplements():
    with pytest.raises(ValueError, match="require evidence"):
        product_visual_context_from_understanding(
            _understanding(),
            prohibited_visual_inferences=["charcoal"],
        )


def test_adapter_accepts_supplements_with_explicit_evidence():
    context = product_visual_context_from_understanding(
        _understanding(),
        prohibited_visual_inferences=["charcoal"],
        supplement_evidence_refs=["user_text:no_charcoal"],
    )

    assert context.prohibited_visual_inferences == ("charcoal",)
    assert "user_text:no_charcoal" in context.evidence_refs


def test_adapter_does_not_create_fallback_evidence():
    understanding = ProductUnderstanding(
        product_name="desk lamp",
        broad_category="home_and_living",
        category_path=["home_and_living", "lighting"],
        confidence=0.8,
    )

    with pytest.raises(ValidationError):
        product_visual_context_from_understanding(understanding)


def test_adapter_allows_explicit_confidence_without_inference():
    context = product_visual_context_from_understanding(
        _understanding(),
        confidence=0.5,
    )

    assert context.confidence == 0.5


def test_french_fries_fixture_preserves_explicit_values_only():
    context = build_product_visual_context(
        product_name="감자튀김",
        category_path=["food_and_beverage", "side_dish", "fried_potato"],
        product_tags=["fried_potato", "crispy_food", "side_dish"],
        visible_attributes=["golden_surface", "thin_cut"],
        explicit_preparation_methods=["fried"],
        permissible_visual_inferences=["crispy_surface", "serving_plate"],
        prohibited_visual_inferences=["charcoal", "open_flame", "grill_marks", "meat"],
        evidence_refs=["user_text:product_name", "user_text:preparation_method", "vision:product_image:visible_attributes"],
        confidence=0.95,
    )

    assert context.product_name == "감자튀김"
    assert context.permissible_visual_inferences == ("crispy_surface", "serving_plate")
    assert context.prohibited_visual_inferences == ("charcoal", "open_flame", "grill_marks", "meat")


def test_pork_belly_fixture_preserves_explicit_values_only():
    context = build_product_visual_context(
        product_name="삼겹살",
        category_path=["food_and_beverage", "meat", "pork"],
        product_tags=["pork", "grilled_meat"],
        explicit_preparation_methods=["table_grilled"],
        permissible_visual_inferences=["grill", "charcoal", "smoke"],
        evidence_refs=["user_text:product_name", "user_text:table_grilled"],
        confidence=0.96,
    )

    assert context.product_tags == ("pork", "grilled_meat")
    assert context.permissible_visual_inferences == ("grill", "charcoal", "smoke")


def test_product_name_change_does_not_change_semantic_lists():
    first = build_product_visual_context(product_name="상품 A", product_tags=["tag_x"], evidence_refs=["test:source"], confidence=0.8)
    second = build_product_visual_context(product_name="완전히 새로운 상품 B", product_tags=["tag_x"], evidence_refs=["test:source"], confidence=0.8)

    assert first.product_tags == second.product_tags
    assert first.visible_attributes == second.visible_attributes
    assert first.explicit_preparation_methods == second.explicit_preparation_methods
    assert first.permissible_visual_inferences == second.permissible_visual_inferences
    assert first.prohibited_visual_inferences == second.prohibited_visual_inferences


@pytest.mark.parametrize("category_path", [["food_and_beverage", "side_dish", "fried_potato"], ["food_and_beverage", "meat", "grilled_meat"]])
def test_category_path_does_not_generate_inferences(category_path: list[str]):
    context = build_product_visual_context(
        product_name="Product",
        category_path=category_path,
        evidence_refs=["test:source"],
        confidence=0.8,
    )

    assert context.permissible_visual_inferences == ()
    assert context.prohibited_visual_inferences == ()


@pytest.mark.parametrize("product_name", ["향수", "책상 조명", "운동화", "세럼", "치즈케이크", "호텔 브런치 메뉴", "전자책 구독권"])
def test_holdout_product_names_pass_without_product_specific_rules(product_name: str):
    context = build_product_visual_context(
        product_name=product_name,
        category_path=["open_domain_category"],
        product_tags=["open_domain_tag"],
        evidence_refs=["test:source"],
        confidence=0.8,
    )

    assert context.product_name == product_name
    assert context.product_tags == ("open_domain_tag",)
    assert context.permissible_visual_inferences == ()


def test_business_and_product_context_fields_overlap_only_on_evidence_and_confidence():
    overlap = set(ProductVisualContext.model_fields) & set(BusinessEnvironmentContext.model_fields)

    assert overlap == {"evidence_refs", "confidence"}
