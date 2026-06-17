from __future__ import annotations

from orchestrator.app.llm.visual_routing_integration import (
    CatalogVisualRouteFamilyResolver,
    ImagePromptLegacyVisualRouteResult,
    build_fail_open_visual_routing_metadata,
    build_image_prompt_visual_routing_metadata,
    build_visual_semantic_intent_for_shadow,
    build_visual_strategy_context_for_shadow,
    build_visual_strategy_runtime_context,
    observe_legacy_visual_route,
    resolve_visual_routing_mode,
)
from orchestrator.app.llm.domain_routing import (
    CanonicalBusinessDomain,
    DomainRoutingResult,
    DomainSupportStatus,
    RoutingEvidenceSource,
    RoutingTagEvidence,
    normalize_business_type,
    project_to_legacy_visual_route,
)
from orchestrator.app.llm.visual_presets import select_visual_preset
from orchestrator.app.llm.visual_templates import select_visual_template
from orchestrator.app.schemas.llm_marketing import AdFormatSpec, MarketingContext
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_routing_shadow import LegacyVisualRouteObservation, RoutingMode, RoutingSource


def test_a8_visual_routing_mode_defaults_to_shadow():
    assert resolve_visual_routing_mode({}) == RoutingMode.SHADOW


def test_a8_visual_routing_mode_reads_render_options():
    state = {"render_options": {"visual_routing_mode": "legacy"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.LEGACY


def test_a8_visual_routing_mode_rejects_canonical_for_first_shadow_pr():
    state = {"render_options": {"visual_routing_mode": "canonical"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.SHADOW


def test_a8_fail_open_metadata_is_sanitized():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=RuntimeError("contains user prompt or secret"),
        stage="trace_build",
    )

    assert metadata == {
        "routing_mode": "shadow",
        "active_source": RoutingSource.LEGACY.value,
        "trace_available": False,
        "trace_error": {
            "stage": "trace_build",
            "exception_type": "RuntimeError",
        },
    }
    assert "secret" not in str(metadata)


def test_a8_fail_open_metadata_sanitizes_unknown_trace_stage():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=RuntimeError("contains user prompt or secret"),
        stage="contains user prompt or secret",
    )

    assert metadata["trace_error"] == {
        "stage": "unknown",
        "exception_type": "RuntimeError",
    }
    metadata_text = str(metadata)
    assert "contains user prompt or secret" not in metadata_text
    assert "secret" not in metadata_text


def test_a8_fail_open_metadata_preserves_known_exception_type():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=ValueError("contains user prompt or secret"),
        stage="trace_build",
    )

    assert metadata["trace_error"] == {
        "stage": "trace_build",
        "exception_type": "ValueError",
    }


def test_a8_fail_open_metadata_sanitizes_unknown_exception_type():
    class PromptSecretLeakingError(Exception):
        pass

    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=PromptSecretLeakingError("contains user prompt or secret"),
        stage="trace_build",
    )

    assert metadata["trace_error"] == {
        "stage": "trace_build",
        "exception_type": "UnexpectedError",
    }
    metadata_text = str(metadata)
    assert "PromptSecretLeakingError" not in metadata_text
    assert "contains user prompt or secret" not in metadata_text
    assert "secret" not in metadata_text


def test_a8_builds_shadow_strategy_context_from_product_understanding_and_marketing_context():
    state = {
        "product_understanding": {
            "product_name": "Cica Serum",
            "normalized_product_type": "cica_serum",
            "broad_category": "beauty_and_personal_care",
            "category_path": ["beauty_and_personal_care", "skincare", "serum"],
            "product_name_evidence_ids": ["state:product_understanding.product_name"],
            "confidence": 0.88,
        },
        "ad_format_spec": {
            "ad_format": "instagram_feed",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": "1:1",
        },
        "campaign_context": {"campaign_intent": "new_product_launch"},
        "current_brief": {"campaign_intent": "new_product_launch"},
    }
    marketing_context = MarketingContext(
        item_or_service="Cica Serum",
        business_type="beauty_skincare",
        promotion_goal="new_product_launch",
    )
    domain = _domain_result(
        raw_business_type="beauty_skincare",
        canonical_domain=CanonicalBusinessDomain.BEAUTY,
        business_tags=["skincare"],
    )

    context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
    )

    assert context.product.product_name == "Cica Serum"
    assert context.product_visual.product_name == "Cica Serum"
    assert context.product_visual.category_path == ("beauty_and_personal_care", "skincare", "serum")
    assert context.product_visual.evidence_refs == ("state:product_understanding.product_name",)
    assert "skincare" in context.business.business_tags
    assert context.campaign.campaign_intent == "new_product_launch"
    assert context.campaign.promotion_goal == "new_product_launch"
    assert context.campaign.evidence_refs == ("state:campaign_context.campaign_intent", "state:context.promotion_goal")
    assert context.ad_format.ad_format == "instagram_feed"
    assert context.ad_format.platform == "instagram"
    assert context.ad_format.output_strategy == "generate_text_free_background_then_overlay"


def test_a8_runtime_context_maps_campaign_intent_to_roles():
    runtime = build_visual_strategy_runtime_context(
        state={"campaign_context": {"campaign_intent": "store_opening"}},
        ad_format_spec={"ad_format": "banner", "width": 1200, "height": 675, "aspect_ratio": "16:9"},
    )

    assert runtime.campaign_roles == frozenset({"announcement"})


def test_a8_runtime_context_maps_launch_and_service_intents_to_safe_roles():
    assert build_visual_strategy_runtime_context(
        state={"campaign_context": {"campaign_intent": "new_product_launch"}},
        ad_format_spec={"ad_format": "banner", "width": 1200, "height": 675, "aspect_ratio": "16:9"},
    ).campaign_roles == frozenset({"promotion"})
    assert build_visual_strategy_runtime_context(
        state={"campaign_context": {"campaign_intent": "new_menu_launch"}},
        ad_format_spec={"ad_format": "banner", "width": 1200, "height": 675, "aspect_ratio": "16:9"},
    ).campaign_roles == frozenset({"promotion"})
    assert build_visual_strategy_runtime_context(
        state={"campaign_context": {"campaign_intent": "service_launch"}},
        ad_format_spec={"ad_format": "banner", "width": 1200, "height": 675, "aspect_ratio": "16:9"},
    ).campaign_roles == frozenset({"information"})


def test_a8_partial_product_understanding_mapping_is_backfilled_with_defaults():
    context = build_visual_strategy_context_for_shadow(
        state={"product_understanding": {"product_name": "Widget"}},
        marketing_context=MarketingContext(item_or_service="Widget"),
        domain_result=_domain_result(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["retail"],
        ),
    )

    assert context.product.product_name == "Widget"
    assert context.product.broad_category == "other"
    assert context.product.category_path == ["other"]
    assert context.product.product_name_evidence_ids == ["state:context.item_or_service"]
    assert context.product.confidence == 0.5
    assert context.product_visual.evidence_refs == ("state:context.item_or_service",)


def test_a8_minimal_restaurant_bbq_context_does_not_infer_product_visual_evidence_from_business_type():
    state = {
        "ad_format_spec": {
            "ad_format": "instagram_feed",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": "1:1",
        }
    }
    marketing_context = MarketingContext(
        item_or_service="Dinner special",
        business_type="restaurant_bbq",
    )
    domain = _domain_result(
        raw_business_type="restaurant_bbq",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        business_tags=["restaurant", "korean_bbq"],
    )

    context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain,
    )

    assert "korean_bbq" in context.business.business_tags
    assert "grilled_meat" not in context.product_visual.product_tags
    assert "grilled_meat" not in context.product_visual.visible_attributes
    assert "table_grilled" not in context.product_visual.explicit_preparation_methods


def test_a8_mapping_product_visual_context_empty_category_and_evidence_are_backfilled():
    context = build_visual_strategy_context_for_shadow(
        state={
            "product_understanding": {
                "product_name": "Cica Serum",
                "broad_category": "beauty_and_personal_care",
                "category_path": ["beauty_and_personal_care", "skincare", "serum"],
                "product_name_evidence_ids": ["state:product"],
                "confidence": 0.8,
            },
            "product_visual_context": {
                "product_name": "Cica Serum",
                "category_path": [],
                "product_tags": ["serum_bottle"],
                "visible_attributes": ["green_label"],
                "explicit_preparation_methods": ["dropper_application"],
                "evidence_refs": [],
                "confidence": 0.76,
            },
        },
        marketing_context=MarketingContext(item_or_service="Cica Serum"),
        domain_result=_domain_result(
            raw_business_type="beauty_skincare",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            business_tags=["skincare"],
        ),
    )

    assert context.product_visual.category_path == ("beauty_and_personal_care", "skincare", "serum")
    assert context.product_visual.evidence_refs == ("state:product",)
    assert context.product_visual.product_tags == ("serum_bottle",)
    assert context.product_visual.visible_attributes == ("green_label",)
    assert context.product_visual.explicit_preparation_methods == ("dropper_application",)


def test_a8_mapping_product_visual_context_none_confidence_is_backfilled():
    context = build_visual_strategy_context_for_shadow(
        state={
            "product_understanding": {
                "product_name": "Cica Serum",
                "broad_category": "beauty_and_personal_care",
                "category_path": ["beauty_and_personal_care", "skincare", "serum"],
                "product_name_evidence_ids": ["state:product"],
                "confidence": 0.8,
            },
            "product_visual_context": {
                "product_name": "Cica Serum",
                "category_path": ["beauty_and_personal_care", "skincare", "serum"],
                "product_tags": ["serum_bottle"],
                "evidence_refs": ["vision:serum_bottle"],
                "confidence": None,
            },
        },
        marketing_context=MarketingContext(item_or_service="Cica Serum"),
        domain_result=_domain_result(
            raw_business_type="beauty_skincare",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            business_tags=["skincare"],
        ),
    )

    assert context.product_visual.confidence == 0.8
    assert context.product_visual.product_tags == ("serum_bottle",)


def test_a8_existing_product_visual_context_empty_category_is_backfilled():
    product_visual = ProductVisualContext(
        product_name="Cica Serum",
        product_tags=["serum_bottle"],
        category_path=[],
        evidence_refs=["vision:serum_bottle"],
        confidence=0.76,
    )

    context = build_visual_strategy_context_for_shadow(
        state={
            "product_understanding": {
                "product_name": "Cica Serum",
                "broad_category": "beauty_and_personal_care",
                "category_path": ["beauty_and_personal_care", "skincare", "serum"],
                "product_name_evidence_ids": ["state:product"],
                "confidence": 0.8,
            },
            "product_visual_context": product_visual,
        },
        marketing_context=MarketingContext(item_or_service="Cica Serum"),
        domain_result=_domain_result(
            raw_business_type="beauty_skincare",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            business_tags=["skincare"],
        ),
    )

    assert context.product_visual.category_path == ("beauty_and_personal_care", "skincare", "serum")
    assert context.product_visual.evidence_refs == ("vision:serum_bottle",)
    assert context.product_visual.product_tags == ("serum_bottle",)


def test_a8_visual_semantic_intent_uses_only_open_evidence_tokens_and_style_tone():
    routing_context = build_visual_strategy_context_for_shadow(
        state={
            "product_understanding": {
                "product_name": "Cica Serum",
                "broad_category": "beauty_and_personal_care",
                "category_path": ["beauty_and_personal_care", "skincare", "serum"],
                "product_name_evidence_ids": ["state:product"],
                "confidence": 0.8,
            },
            "product_visual_context": {
                "product_name": "Cica Serum",
                "product_tags": ["serum_bottle"],
                "visible_attributes": ["green_label"],
                "explicit_preparation_methods": ["dropper_application"],
                "prohibited_visual_inferences": ["medical_result"],
                "evidence_refs": ["vision:serum_bottle"],
                "confidence": 0.76,
            },
            "text_style_spec": {"profile": "calm_minimal", "template_id": "tmpl_hidden"},
            "selected_template_id": "preset_beauty_hero",
            "requested_template_id": "preset_request",
        },
        marketing_context=MarketingContext(item_or_service="Cica Serum", brand_tone="fresh"),
        domain_result=_domain_result(
            raw_business_type="beauty_skincare",
            canonical_domain=CanonicalBusinessDomain.BEAUTY,
            business_tags=["skincare"],
        ),
    )

    intent = build_visual_semantic_intent_for_shadow(
        {
            "text_style_spec": {"profile": "calm_minimal", "template_id": "tmpl_hidden"},
            "selected_template_id": "preset_beauty_hero",
            "requested_template_id": "preset_request",
        },
        routing_context,
    )

    assert intent.required_visual_facts == ("serum_bottle", "green_label", "dropper_application")
    assert intent.prohibited_visual_elements == ("medical_result",)
    assert intent.desired_moods == ("calm_minimal",)
    intent_text = str(intent.model_dump())
    assert "preset_beauty_hero" not in intent_text
    assert "preset_request" not in intent_text
    assert "tmpl_hidden" not in intent_text


def test_a8_runtime_context_uses_ad_format_as_placement_and_empty_campaign_roles_by_default():
    runtime = build_visual_strategy_runtime_context(
        state={"selected_ad_format": "instagram_story"},
        ad_format_spec={
            "ad_format": "instagram_feed",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": "1:1",
        },
    )

    assert runtime.placement == "instagram_feed"
    assert runtime.campaign_roles == frozenset()


def test_a8_invalid_ad_format_values_are_sanitized_to_safe_defaults():
    state = {
        "ad_format_spec": {
            "ad_format": "unsupported_story",
            "platform": "unsupported_platform",
            "aspect_ratio": "2:3",
            "width": 0,
            "height": -1,
            "information_density": "dense",
            "visual_priority": "invalid_priority",
            "output_strategy": "unknown_strategy",
        }
    }

    context = build_visual_strategy_context_for_shadow(
        state=state,
        marketing_context=MarketingContext(item_or_service="Widget"),
        domain_result=_domain_result(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["retail"],
        ),
    )

    assert context.ad_format.ad_format == "instagram_feed"
    assert context.ad_format.platform == "instagram"
    assert context.ad_format.aspect_ratio == "1:1"
    assert context.ad_format.width == 1024
    assert context.ad_format.height == 1024
    assert context.ad_format.information_density == "medium"
    assert context.ad_format.visual_priority == "mood_first"
    assert context.ad_format.output_strategy == "generate_text_free_background_then_overlay"


def test_a8_valid_ad_format_values_are_preserved():
    runtime = build_visual_strategy_runtime_context(
        state={},
        ad_format_spec={
            "ad_format": "poster",
            "platform": "offline",
            "aspect_ratio": "A4_vertical",
            "width": 768,
            "height": 1024,
            "information_density": "high",
            "visual_priority": "information_first",
            "output_strategy": "template_composite",
        },
    )
    context = build_visual_strategy_context_for_shadow(
        state={
            "ad_format_spec": {
                "ad_format": "poster",
                "platform": "offline",
                "aspect_ratio": "A4_vertical",
                "width": 768,
                "height": 1024,
                "information_density": "high",
                "visual_priority": "information_first",
                "output_strategy": "template_composite",
            }
        },
        marketing_context=MarketingContext(item_or_service="Widget"),
        domain_result=_domain_result(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["retail"],
        ),
    )

    assert runtime.placement == "poster"
    assert context.ad_format.platform == "offline"
    assert context.ad_format.aspect_ratio == "A4_vertical"
    assert context.ad_format.width == 768
    assert context.ad_format.height == 1024
    assert context.ad_format.information_density == "high"
    assert context.ad_format.visual_priority == "information_first"
    assert context.ad_format.output_strategy == "template_composite"


def test_a8_ad_format_spec_instance_is_preserved_for_context_and_runtime():
    ad_format = AdFormatSpec(
        ad_format="poster",
        platform="offline",
        aspect_ratio="A4_vertical",
        width=768,
        height=1024,
        information_density="high",
        visual_priority="information_first",
        output_strategy="template_composite",
        metadata={"source": "unit_test"},
    )

    runtime = build_visual_strategy_runtime_context(
        state={},
        ad_format_spec=ad_format,
    )
    context = build_visual_strategy_context_for_shadow(
        state={"ad_format_spec": ad_format},
        marketing_context=MarketingContext(item_or_service="Widget"),
        domain_result=_domain_result(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["retail"],
        ),
    )

    assert runtime.placement == "poster"
    assert context.ad_format.ad_format == "poster"
    assert context.ad_format.platform == "offline"
    assert context.ad_format.aspect_ratio == "A4_vertical"
    assert context.ad_format.width == 768
    assert context.ad_format.height == 1024
    assert context.ad_format.information_density == "high"
    assert context.ad_format.visual_priority == "information_first"
    assert context.ad_format.output_strategy == "template_composite"
    assert context.ad_format.metadata == {"source": "unit_test"}


def test_a8_invalid_ad_format_metadata_defaults_to_empty_dict():
    context = build_visual_strategy_context_for_shadow(
        state={"ad_format_spec": {"metadata": "not-a-mapping"}},
        marketing_context=MarketingContext(item_or_service="Widget"),
        domain_result=_domain_result(
            raw_business_type="retail",
            canonical_domain=CanonicalBusinessDomain.RETAIL,
            business_tags=["retail"],
        ),
    )

    assert context.ad_format.metadata == {}


def test_a8_observes_legacy_visual_route_without_copy_tone_binding():
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    preset = select_visual_preset(projection.route_key.value)
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    observation = observe_legacy_visual_route(
        ImagePromptLegacyVisualRouteResult(
            legacy_projection=projection,
            template_id=template.template_id,
            preset_id=preset["preset_id"],
            route_family_id="restaurant_bbq",
        )
    )

    assert isinstance(observation, LegacyVisualRouteObservation)
    assert observation.legacy_route_key == projection.route_key
    assert observation.template_id == "restaurant_bbq_warm_grill"
    assert observation.preset_id == "restaurant_bbq_warm_grill"
    assert observation.copy_tone_profile_id is None
    assert observation.route_family_id == "restaurant_bbq"
    assert observation.route_version == projection.projection_version


def test_a8_catalog_visual_route_family_resolver_resolves_known_matching_resources():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("restaurant_bbq_warm_grill", "restaurant_bbq_warm_grill") == "restaurant_bbq"
    assert resolver.resolve_family("restaurant_generic_clean", "restaurant_generic_clean") == "restaurant"
    assert resolver.resolve_family("generic_clean_ad_background", "generic_clean_ad_background") == "generic"


def test_a8_catalog_visual_route_family_resolver_rejects_mixed_resource_pair():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("restaurant_bbq_warm_grill", "restaurant_generic_clean") is None


def test_a8_catalog_visual_route_family_resolver_rejects_multi_business_template_mapping():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("beauty_skincare_clean_premium", "beauty_salon_clean_pastel") is None


def test_a8_catalog_visual_route_family_resolver_rejects_unknown_resources():
    resolver = CatalogVisualRouteFamilyResolver()

    assert resolver.resolve_family("unknown_preset", "restaurant_bbq_warm_grill") is None
    assert resolver.resolve_family("restaurant_bbq_warm_grill", "unknown_template") is None


def test_a8_builds_successful_shadow_metadata_for_bbq_evidence():
    marketing_context = MarketingContext(
        business_type="restaurant_bbq",
        item_or_service="삼겹살",
        promotion_goal="new_menu",
        brand_tone="premium",
    )
    state = {
        "ad_format_spec": {
            "ad_format": "instagram_feed",
            "width": 1024,
            "height": 1024,
            "aspect_ratio": "1:1",
        },
        "product_understanding": {
            "product_name": "삼겹살",
            "broad_category": "food_and_beverage",
            "category_path": ["food_and_beverage", "restaurant", "korean_bbq"],
            "product_name_evidence_ids": ["state:context.item_or_service"],
            "confidence": 0.9,
        },
        "product_visual_context": {
            "product_name": "삼겹살",
            "category_path": ["food_and_beverage", "restaurant", "korean_bbq"],
            "product_tags": ["grilled_meat"],
            "explicit_preparation_methods": ["table_grilled"],
            "permissible_visual_inferences": ["charcoal"],
            "evidence_refs": ["vision:grilled_meat", "menu:charcoal"],
            "confidence": 0.86,
        },
    }
    domain = normalize_business_type("restaurant_bbq")
    domain_result = _domain_result(
        raw_business_type="restaurant_bbq",
        canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
        business_tags=["restaurant", "korean_bbq"],
    )
    projection = project_to_legacy_visual_route(
        domain,
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    preset = select_visual_preset(projection.route_key.value)
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=domain_result,
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["metadata_version"]
    assert metadata["routing_mode"] == "shadow"
    assert metadata["active_source"] == "legacy"
    assert metadata["trace_available"] is True
    trace = metadata["trace"]
    assert trace["routing_mode"] == "shadow"
    assert trace["active_route"]["source"] == "legacy"
    assert trace["active_route"]["copy_tone_profile_id"] is None
    assert trace["legacy_observation"]["legacy_route_key"] == "restaurant_bbq"
    assert trace["legacy_observation"]["copy_tone_profile_id"] is None
    assert trace["canonical_decision"]["strategy_id"] == "restaurant_bbq_warm_grill"
    assert trace["route_disagreement"]["new_strategy_id"] == "restaurant_bbq_warm_grill"


def test_a8_legacy_mode_skips_canonical_resolver(monkeypatch):
    def raise_if_called(*args, **kwargs):
        raise AssertionError("canonical resolver should not run in legacy mode")

    monkeypatch.setattr(
        "orchestrator.app.llm.visual_strategy_resolver.resolve_visual_strategy",
        raise_if_called,
    )
    marketing_context = MarketingContext(item_or_service="삼겹살", business_type="restaurant_bbq")
    state = {
        "render_options": {"visual_routing_mode": "legacy"},
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"},
    }
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    preset = select_visual_preset(projection.route_key.value)
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=_domain_result(
            raw_business_type="restaurant_bbq",
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["restaurant", "korean_bbq"],
        ),
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["routing_mode"] == "legacy"
    assert metadata["active_source"] == "legacy"
    assert metadata["trace_available"] is True
    assert metadata["trace"]["routing_mode"] == "legacy"
    assert "canonical_decision" not in metadata["trace"]


def test_a8_shadow_canonical_resolver_failure_returns_partial_metadata(monkeypatch):
    def raise_canonical_error(*args, **kwargs):
        raise RuntimeError("secret prompt")

    monkeypatch.setattr(
        "orchestrator.app.llm.visual_strategy_resolver.resolve_visual_strategy",
        raise_canonical_error,
    )
    marketing_context = MarketingContext(item_or_service="삼겹살", business_type="restaurant_bbq")
    state = {
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"}
    }
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    preset = select_visual_preset(projection.route_key.value)
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=_domain_result(
            raw_business_type="restaurant_bbq",
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["restaurant", "korean_bbq"],
        ),
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["routing_mode"] == "shadow"
    assert metadata["active_source"] == "legacy"
    assert metadata["trace_available"] is True
    assert metadata["trace"]["completeness"] == "partial"
    assert metadata["trace"]["shadow_error"]["code"] == "canonical_resolution_failed"
    assert "secret" not in str(metadata)


def test_a8_shadow_canonical_custom_exception_type_is_sanitized(monkeypatch):
    class PromptSecretLeakingError(Exception):
        pass

    def raise_canonical_error(*args, **kwargs):
        raise PromptSecretLeakingError("secret prompt")

    monkeypatch.setattr(
        "orchestrator.app.llm.visual_strategy_resolver.resolve_visual_strategy",
        raise_canonical_error,
    )
    marketing_context = MarketingContext(item_or_service="삼겹살", business_type="restaurant_bbq")
    state = {
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"}
    }
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    preset = select_visual_preset(projection.route_key.value)
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=_domain_result(
            raw_business_type="restaurant_bbq",
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["restaurant", "korean_bbq"],
        ),
        legacy_projection=projection,
        visual_template=template,
        preset=preset,
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["trace"]["shadow_error"]["exception_type"] == "UnexpectedError"
    metadata_text = str(metadata)
    assert "PromptSecretLeakingError" not in metadata_text
    assert "secret prompt" not in metadata_text


def test_a8_unexpected_builder_failure_returns_sanitized_fallback_metadata():
    marketing_context = MarketingContext(item_or_service="삼겹살", business_type="restaurant_bbq")
    state = {
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024, "aspect_ratio": "1:1"}
    }
    projection = project_to_legacy_visual_route(
        normalize_business_type("restaurant_bbq"),
        product_tags={"grilled_meat"},
        explicit_scene_tags=set(),
    )
    template = select_visual_template(projection.route_key.value, "instagram_feed", "premium")

    metadata = build_image_prompt_visual_routing_metadata(
        state=state,
        marketing_context=marketing_context,
        domain_result=_domain_result(
            raw_business_type="restaurant_bbq",
            canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
            business_tags=["restaurant", "korean_bbq"],
        ),
        legacy_projection=projection,
        visual_template=template,
        preset={},
        ad_format_spec=state["ad_format_spec"],
        route_family_id="restaurant_bbq",
    )

    assert metadata["trace_available"] is False
    assert metadata["trace_error"] == {
        "stage": "visual_routing_shadow",
        "exception_type": "KeyError",
    }
    assert "preset_id" not in str(metadata)


def _domain_result(
    *,
    raw_business_type: str,
    canonical_domain: CanonicalBusinessDomain,
    business_tags: list[str],
) -> DomainRoutingResult:
    return DomainRoutingResult(
        raw_business_type=raw_business_type,
        canonical_domain=canonical_domain,
        support_status=DomainSupportStatus.SPECIALIZED,
        business_tags=[
            RoutingTagEvidence(
                tag=tag,
                source=RoutingEvidenceSource.USER_TEXT,
                confidence=0.9,
                evidence_ref=f"user_text:business_type:{tag}",
            )
            for tag in business_tags
        ],
        evidence_refs=["user_text:business_type"],
        confidence=0.9,
    )
