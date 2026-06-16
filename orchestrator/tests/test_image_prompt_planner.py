import orchestrator.app.graph.nodes  # noqa: F401

from orchestrator.app.llm.nodes.image_prompt_planner import build_image_prompt_spec_with_critic
from orchestrator.app.schemas.text_layout import NormalizedBBox, TextLayoutSpec
from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource


def _state(business_type: str, reference_template: dict | None = None) -> dict:
    layout = TextLayoutSpec(
        template="top_headline_center_product_bottom_cta",
        canvas_width=1024,
        canvas_height=1024,
        reserved_text_areas=[NormalizedBBox(x=0.08, y=0.08, w=0.84, h=0.16)],
        slots=[],
    )
    return {
        "context": {"business_type": business_type, "item_or_service": "대표 상품", "brand_tone": "premium"},
        "ad_format_spec": {"width": 1024, "height": 1024, "aspect_ratio": "1:1", "ad_format": "instagram_feed"},
        "text_layout_spec": layout.model_dump(),
        "text_style_spec": {"profile": "premium"},
        "selected_reference_template": reference_template or {},
    }


def _with_product_visual_context(state: dict, *, product_tags: list[str]) -> dict:
    state = dict(state)
    state["product_visual_context"] = {
        "product_name": state["context"]["item_or_service"],
        "product_tags": product_tags,
        "evidence_refs": ["test:product_visual_context"],
        "confidence": 0.95,
    }
    return state


def _assert_single_resolved_visual_key(
    metadata: dict,
    *,
    route_key: str,
    preset_id: str,
    template_id: str,
):
    assert metadata["resolved_visual_route_key"] == route_key
    assert metadata["visual_template_id"] == template_id
    assert metadata["business_visual_preset_id"] == preset_id
    assert metadata["scene_plan"]["business_type"] == route_key
    assert metadata["legacy_routing_projection"]["route_key"] == route_key


def test_image_prompt_uses_visual_template_and_safety_terms():
    spec = build_image_prompt_spec_with_critic(_state("cafe"))

    assert spec.metadata["visual_template_id"] == "cafe_dessert_soft_premium"
    assert "Reserve clean negative space for Korean text overlay" in spec.positive_prompt_en
    negative = spec.negative_prompt_en.lower()
    for term in ["text", "letters", "numbers", "hangul", "korean characters", "logo", "watermark", "typography", "caption", "signage"]:
        assert term in negative
    assert spec.must_not_include_text is True
    assert spec.reserved_text_areas


def test_image_prompt_template_selection_variants():
    assert build_image_prompt_spec_with_critic(_state("restaurant")).metadata["visual_template_id"] == "restaurant_generic_clean"
    assert build_image_prompt_spec_with_critic(_state("restaurant_bbq")).metadata["visual_template_id"] == "restaurant_generic_clean"
    assert build_image_prompt_spec_with_critic(_state("beauty")).metadata["visual_template_id"] == "generic_clean_ad_background"
    assert build_image_prompt_spec_with_critic(_state("beauty_skincare")).metadata["visual_template_id"] == "beauty_salon_clean_pastel"
    assert build_image_prompt_spec_with_critic(_state("unknown")).metadata["visual_template_id"] == "generic_clean_ad_background"


def test_image_prompt_single_resolved_key_downgrades_legacy_bbq_without_visual_evidence():
    spec = build_image_prompt_spec_with_critic(_state("restaurant_bbq"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="restaurant",
        preset_id="restaurant_generic_clean",
        template_id="restaurant_generic_clean",
    )
    assert "korean_bbq_without_visual_evidence" in metadata["legacy_routing_projection"]["reason_codes"]


def test_image_prompt_single_resolved_key_allows_bbq_with_grilled_meat_product_evidence():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="restaurant_bbq",
        preset_id="restaurant_bbq_warm_grill",
        template_id="restaurant_bbq_warm_grill",
    )


def test_a8_shadow_metadata_preserves_legacy_production_route():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="restaurant_bbq",
        preset_id="restaurant_bbq_warm_grill",
        template_id="restaurant_bbq_warm_grill",
    )
    visual_routing = metadata["visual_routing"]
    assert visual_routing["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["active_source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace_available"] is True
    assert visual_routing["trace"]["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["trace"]["active_route"]["source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace"]["active_route"]["preset_id"] == "restaurant_bbq_warm_grill"
    assert visual_routing["trace"]["active_route"]["template_id"] == "restaurant_bbq_warm_grill"


def test_a8_shadow_metadata_does_not_rebind_copy_tone_from_visual_route():
    state = _with_product_visual_context(
        _state("restaurant_bbq"),
        product_tags=["pork", "grilled_meat"],
    )

    spec = build_image_prompt_spec_with_critic(state)
    visual_routing = spec.metadata["visual_routing"]
    legacy = visual_routing["trace"]["legacy_observation"]

    assert spec.metadata["resolved_visual_route_key"] == "restaurant_bbq"
    assert legacy["copy_tone_profile_id"] is None
    assert visual_routing["trace"]["active_route"]["copy_tone_profile_id"] is None


def test_a8_shadow_metadata_fail_open_when_canonical_resolution_fails(monkeypatch):
    def raise_canonical_error(*args, **kwargs):
        raise RuntimeError("canonical resolver unavailable")

    monkeypatch.setattr(
        "orchestrator.app.llm.visual_strategy_resolver.resolve_visual_strategy",
        raise_canonical_error,
    )

    spec = build_image_prompt_spec_with_critic(_state("cafe"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="cafe",
        preset_id="cafe_dessert_soft_premium",
        template_id="cafe_dessert_soft_premium",
    )
    visual_routing = metadata["visual_routing"]
    assert visual_routing["routing_mode"] == RoutingMode.SHADOW.value
    assert visual_routing["active_source"] == RoutingSource.LEGACY.value
    assert visual_routing["trace_available"] is True
    assert visual_routing["trace"]["completeness"] == "partial"
    assert visual_routing["trace"]["shadow_error"]["code"] == "canonical_resolution_failed"


def test_image_prompt_single_resolved_key_preserves_unsupported_fallback_breadcrumb():
    spec = build_image_prompt_spec_with_critic(_state("fitness"))
    metadata = spec.metadata

    _assert_single_resolved_visual_key(
        metadata,
        route_key="generic",
        preset_id="generic_clean_ad_background",
        template_id="generic_clean_ad_background",
    )
    assert metadata["domain_routing_result"]["unsupported_domain_hint"] == "fitness"
    assert metadata["legacy_routing_projection"]["fallback_reason"] == "unsupported_domain_in_mvp"


def test_image_prompt_single_resolved_key_covers_ambiguous_and_visual_fallback_cases():
    cases = [
        {
            "business_type": "beauty_salon",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "needs_evidence",
            "domain_fallback_reason": "ambiguous_beauty_subdomain",
            "projection_fallback_reason": "ambiguous_beauty_subdomain",
            "unsupported_domain_hint": None,
        },
        {
            "business_type": "retail",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "specialized",
            "domain_fallback_reason": None,
            "projection_fallback_reason": "no_specialized_visual_profile",
            "unsupported_domain_hint": None,
        },
        {
            "business_type": "education",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "generic_fallback",
            "domain_fallback_reason": "unsupported_domain_in_mvp",
            "projection_fallback_reason": "unsupported_domain_in_mvp",
            "unsupported_domain_hint": "education",
        },
        {
            "business_type": "service",
            "route_key": "generic",
            "preset_id": "generic_clean_ad_background",
            "template_id": "generic_clean_ad_background",
            "support_status": "generic_fallback",
            "domain_fallback_reason": "unsupported_domain_in_mvp",
            "projection_fallback_reason": "unsupported_domain_in_mvp",
            "unsupported_domain_hint": "service",
        },
    ]

    for case in cases:
        spec = build_image_prompt_spec_with_critic(_state(case["business_type"]))
        metadata = spec.metadata
        domain = metadata["domain_routing_result"]
        projection = metadata["legacy_routing_projection"]

        _assert_single_resolved_visual_key(
            metadata,
            route_key=case["route_key"],
            preset_id=case["preset_id"],
            template_id=case["template_id"],
        )
        assert domain["support_status"] == case["support_status"]
        assert domain.get("fallback_reason") == case["domain_fallback_reason"]
        assert domain.get("unsupported_domain_hint") == case["unsupported_domain_hint"]
        assert projection.get("fallback_reason") == case["projection_fallback_reason"]


def test_reference_template_preset_id_cannot_override_resolved_visual_key():
    state = _state(
        "unknown",
        {
            "title": "Legacy BBQ Reference",
            "preset_id": "restaurant_bbq_warm_grill",
            "visual_template_id": "restaurant_bbq_warm_grill",
        },
    )

    spec = build_image_prompt_spec_with_critic(state)
    metadata = spec.metadata

    assert metadata["resolved_visual_route_key"] == "generic"
    assert metadata["visual_template_id"] == "generic_clean_ad_background"
    assert metadata["business_visual_preset_id"] == "generic_clean_ad_background"
    assert metadata["scene_plan"]["business_type"] == "generic"


def test_image_prompt_scene_planner_does_not_infer_bbq_from_raw_user_input():
    state = _state("restaurant")
    state["user_input"] = "숯불 삼겹살 맛집 포스터 만들어줘"

    spec = build_image_prompt_spec_with_critic(state)

    assert spec.metadata["business_visual_preset_id"] == "restaurant_generic_clean"
    assert spec.metadata["scene_plan"]["business_type"] == "restaurant"


def test_image_prompt_keeps_reference_template_hint():
    reference = {"title": "Pastel Beauty", "style_keywords": ["skincare"], "layout_hint": "clean_text_space"}
    spec = build_image_prompt_spec_with_critic(_state("unknown", reference))

    assert spec.metadata["selected_reference_template"]["title"] == "Pastel Beauty"
    assert "Pastel Beauty" in spec.positive_prompt_en
