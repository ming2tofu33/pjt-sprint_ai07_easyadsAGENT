"""Default declarative visual strategy profile snapshots."""

from __future__ import annotations

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry, build_visual_strategy_resource_catalog
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)


def build_default_visual_strategy_profiles(
    resources: VisualStrategyResourceCatalog,
) -> tuple[VisualStrategyProfile, ...]:
    """Build default profiles using only IDs present in the supplied resources."""

    candidates = (
        VisualStrategyProfile(
            strategy_id="generic_clean_ad_background",
            archetype="clean_ad_background",
            supported_domains=frozenset(CanonicalBusinessDomain),
            supported_placements=frozenset(),
            required_tags=frozenset(),
            preferred_tags=frozenset({"clean", "neutral", "premium"}),
            excluded_tags=frozenset(),
            composition_template_id="generic_clean_ad_background",
            mood_preset_id="generic_clean_ad_background",
            copy_tone_profile_id="generic_v1",
            provider_capabilities=frozenset(),
            priority=10,
            fallback_tier=1,
            enabled=True,
        ),
        VisualStrategyProfile(
            strategy_id="cafe_dessert_soft_premium",
            archetype="product_hero_with_copy_space",
            supported_domains=frozenset({CanonicalBusinessDomain.FOOD_AND_BEVERAGE}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"warm", "premium", "fresh"}),
            excluded_tags=frozenset(),
            composition_template_id="cafe_dessert_soft_premium",
            mood_preset_id="cafe_dessert_soft_premium",
            copy_tone_profile_id="cafe_v1",
            provider_capabilities=frozenset(),
            priority=40,
            enabled=False,
        ),
        VisualStrategyProfile(
            strategy_id="restaurant_clean_food_hero",
            archetype="food_hero_with_copy_space",
            supported_domains=frozenset({CanonicalBusinessDomain.FOOD_AND_BEVERAGE}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "banner", "poster", "flyer"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"appetizing", "clean", "warm"}),
            excluded_tags=frozenset(),
            composition_template_id="restaurant_generic_clean",
            mood_preset_id="restaurant_generic_clean",
            copy_tone_profile_id="generic_v1",
            provider_capabilities=frozenset(),
            priority=35,
            enabled=False,
        ),
        VisualStrategyProfile(
            strategy_id="restaurant_bbq_warm_grill",
            archetype="warm_food_hero_with_copy_space",
            supported_domains=frozenset({CanonicalBusinessDomain.FOOD_AND_BEVERAGE}),
            supported_placements=frozenset({"instagram_feed", "banner", "flyer", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"warm", "bold", "appetizing"}),
            excluded_tags=frozenset(),
            required_tag_requirements=(
                VisualStrategyTagRequirement(
                    source=VisualStrategyContextSource.BUSINESS,
                    all_of=frozenset({"korean_bbq"}),
                ),
                VisualStrategyTagRequirement(
                    source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                    all_of=frozenset({"grilled_meat", "table_grilled"}),
                ),
            ),
            introduced_visual_elements=frozenset({"grill", "smoke", "charcoal", "meat"}),
            visual_element_evidence_requirements=(
                VisualElementEvidenceRequirement(
                    element="grill",
                    requirements=(
                        VisualStrategyTagRequirement(
                            source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                            all_of=frozenset({"grilled_meat", "table_grilled"}),
                        ),
                    ),
                ),
                VisualElementEvidenceRequirement(
                    element="smoke",
                    requirements=(
                        VisualStrategyTagRequirement(
                            source=VisualStrategyContextSource.PRODUCT_VISUAL_INFERENCE,
                            any_of=frozenset({"smoke", "charcoal"}),
                        ),
                    ),
                ),
                VisualElementEvidenceRequirement(
                    element="charcoal",
                    requirements=(
                        VisualStrategyTagRequirement(
                            source=VisualStrategyContextSource.PRODUCT_VISUAL_INFERENCE,
                            any_of=frozenset({"smoke", "charcoal"}),
                        ),
                    ),
                ),
                VisualElementEvidenceRequirement(
                    element="meat",
                    requirements=(
                        VisualStrategyTagRequirement(
                            source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT,
                            any_of=frozenset({"grilled_meat"}),
                        ),
                    ),
                ),
            ),
            composition_template_id="restaurant_bbq_warm_grill",
            mood_preset_id="restaurant_bbq_warm_grill",
            copy_tone_profile_id="restaurant_bbq_v1",
            provider_capabilities=frozenset(),
            priority=35,
            enabled=True,
        ),
        VisualStrategyProfile(
            strategy_id="beauty_skincare_clean_premium",
            archetype="beauty_product_or_service_mood",
            supported_domains=frozenset({CanonicalBusinessDomain.BEAUTY}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"clean", "premium", "gentle"}),
            excluded_tags=frozenset(),
            composition_template_id="beauty_salon_clean_pastel",
            mood_preset_id="beauty_skincare_clean_premium",
            copy_tone_profile_id="beauty_skincare_v1",
            provider_capabilities=frozenset(),
            priority=35,
            enabled=False,
        ),
        VisualStrategyProfile(
            strategy_id="beauty_hair_salon_clean",
            archetype="beauty_service_environment",
            supported_domains=frozenset({CanonicalBusinessDomain.BEAUTY}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"clean", "premium", "stylish"}),
            excluded_tags=frozenset(),
            composition_template_id="beauty_salon_clean_pastel",
            mood_preset_id="beauty_hair_salon_clean",
            copy_tone_profile_id="beauty_hair_v1",
            provider_capabilities=frozenset(),
            priority=30,
            enabled=False,
        ),
        VisualStrategyProfile(
            strategy_id="beauty_nail_clean_detail",
            archetype="beauty_detail_hero",
            supported_domains=frozenset({CanonicalBusinessDomain.BEAUTY}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"delicate", "clean", "mood"}),
            excluded_tags=frozenset(),
            composition_template_id="beauty_salon_clean_pastel",
            mood_preset_id="beauty_nail_clean_detail",
            copy_tone_profile_id="beauty_nail_v1",
            provider_capabilities=frozenset(),
            priority=30,
            enabled=False,
        ),
        VisualStrategyProfile(
            strategy_id="beauty_spa_soft_wellness",
            archetype="beauty_wellness_mood",
            supported_domains=frozenset({CanonicalBusinessDomain.BEAUTY}),
            supported_placements=frozenset({"instagram_feed", "instagram_story", "poster"}),
            required_tags=frozenset(),
            preferred_tags=frozenset({"calm", "wellness", "soft"}),
            excluded_tags=frozenset(),
            composition_template_id="beauty_salon_clean_pastel",
            mood_preset_id="beauty_spa_soft_wellness",
            copy_tone_profile_id="beauty_spa_v1",
            provider_capabilities=frozenset(),
            priority=30,
            enabled=False,
        ),
    )

    available = {
        (
            profile.composition_template_id in resources.composition_template_ids,
            profile.mood_preset_id in resources.mood_preset_ids,
            profile.copy_tone_profile_id in resources.copy_tone_profile_ids,
        )
        for profile in candidates
    }
    if available != {(True, True, True)}:
        missing = next(profile for profile in candidates if profile.composition_template_id not in resources.composition_template_ids or profile.mood_preset_id not in resources.mood_preset_ids or profile.copy_tone_profile_id not in resources.copy_tone_profile_ids)
        raise ValueError(f"default visual strategy references an unknown resource: {missing.strategy_id}")

    return candidates


def build_default_visual_strategy_registry(
    *,
    resources: VisualStrategyResourceCatalog | None = None,
    version: str = "visual-strategy-registry-v1",
) -> VisualStrategyRegistry:
    resource_catalog = resources or build_visual_strategy_resource_catalog()
    return VisualStrategyRegistry(
        version=version,
        profiles=build_default_visual_strategy_profiles(resource_catalog),
        resources=resource_catalog,
    )
