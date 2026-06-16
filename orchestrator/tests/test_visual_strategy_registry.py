from __future__ import annotations

import os
import subprocess
import sys

import pytest

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain
from orchestrator.app.llm.visual_strategy_profiles import (
    build_default_visual_strategy_profiles,
    build_default_visual_strategy_registry,
)
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry, build_visual_strategy_resource_catalog
from orchestrator.app.schemas.visual_strategy import (
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)


def _resources(**overrides) -> VisualStrategyResourceCatalog:
    data = {
        "composition_template_ids": ["template_alpha", "template_beta"],
        "mood_preset_ids": ["preset_alpha", "preset_beta"],
        "copy_tone_profile_ids": ["tone_alpha", "tone_beta"],
        "provider_capability_ids": None,
    }
    data.update(overrides)
    return VisualStrategyResourceCatalog(**data)


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


def test_registry_exposes_read_only_lookup_and_enabled_profiles():
    disabled = _profile(strategy_id="strategy_disabled", priority=100, enabled=False)
    registry = VisualStrategyRegistry(
        version="visual-strategy-registry-v1",
        profiles=[_profile(), disabled],
        resources=_resources(),
    )

    assert registry.version == "visual-strategy-registry-v1"
    assert registry.contains("strategy_alpha")
    assert registry.get("strategy_alpha").strategy_id == "strategy_alpha"
    assert registry.get_optional("missing") is None
    assert [profile.strategy_id for profile in registry.list_profiles()] == ["strategy_alpha"]
    assert [profile.strategy_id for profile in registry.list_profiles(include_disabled=True)] == [
        "strategy_disabled",
        "strategy_alpha",
    ]
    assert not hasattr(registry, "register")
    assert not hasattr(registry, "unregister")
    assert not hasattr(registry, "enable")
    assert not hasattr(registry, "disable")
    assert not hasattr(registry, "update_profile")


def test_registry_rejects_duplicate_strategy_id_even_when_payload_matches():
    profile = _profile()
    with pytest.raises(ValueError, match="duplicate visual strategy ID"):
        VisualStrategyRegistry(version="v1", profiles=[profile, profile], resources=_resources())


@pytest.mark.parametrize(
    "field_name,value,expected_message",
    [
        ("composition_template_id", "missing_template", "unknown composition template ID"),
        ("mood_preset_id", "missing_preset", "unknown mood preset ID"),
        ("copy_tone_profile_id", "missing_tone", "unknown copy tone profile ID"),
    ],
)
def test_registry_rejects_unknown_resource_references(field_name: str, value: str, expected_message: str):
    with pytest.raises(ValueError, match=expected_message):
        VisualStrategyRegistry(
            version="v1",
            profiles=[_profile(**{field_name: value})],
            resources=_resources(),
        )


def test_provider_capability_catalog_is_optional_but_validated_when_supplied():
    VisualStrategyRegistry(
        version="v1",
        profiles=[_profile(provider_capabilities=["capability_alpha"])],
        resources=_resources(provider_capability_ids=None),
    )

    VisualStrategyRegistry(
        version="v1",
        profiles=[_profile(provider_capabilities=["capability_alpha"])],
        resources=_resources(provider_capability_ids=["capability_alpha"]),
    )

    with pytest.raises(ValueError, match="unknown provider capability ID"):
        VisualStrategyRegistry(
            version="v1",
            profiles=[_profile(provider_capabilities=["capability_alpha"])],
            resources=_resources(provider_capability_ids=["capability_beta"]),
        )


def test_provider_capability_none_and_empty_set_have_different_meaning():
    VisualStrategyRegistry(
        version="v1",
        profiles=[_profile(provider_capabilities=["capability_alpha"])],
        resources=_resources(provider_capability_ids=None),
    )
    with pytest.raises(ValueError, match="unknown provider capability ID"):
        VisualStrategyRegistry(
            version="v1",
            profiles=[_profile(provider_capabilities=["capability_alpha"])],
            resources=_resources(provider_capability_ids=[]),
        )


def test_registry_ordering_and_snapshot_hash_are_deterministic():
    lower = _profile(strategy_id="b_strategy", priority=1)
    high_b = _profile(strategy_id="b_high_strategy", priority=20)
    high_a = _profile(strategy_id="a_high_strategy", priority=20)

    registry_a = VisualStrategyRegistry(version="v1", profiles=[lower, high_b, high_a], resources=_resources())
    registry_b = VisualStrategyRegistry(version="v1", profiles=[high_a, lower, high_b], resources=_resources())

    assert [profile.strategy_id for profile in registry_a.list_profiles(include_disabled=True)] == [
        "a_high_strategy",
        "b_high_strategy",
        "b_strategy",
    ]
    assert registry_a.snapshot_hash == registry_b.snapshot_hash


def test_snapshot_hash_is_stable_across_hash_seeds():
    script = (
        "from orchestrator.app.llm.visual_strategy_profiles import build_default_visual_strategy_registry;"
        "print(build_default_visual_strategy_registry().snapshot_hash)"
    )
    env_a = {**os.environ, "PYTHONPATH": ".", "PYTHONHASHSEED": "1"}
    env_b = {**os.environ, "PYTHONPATH": ".", "PYTHONHASHSEED": "2"}

    hash_a = subprocess.check_output([sys.executable, "-c", script], env=env_a, text=True).strip()
    hash_b = subprocess.check_output([sys.executable, "-c", script], env=env_b, text=True).strip()

    assert hash_a == hash_b


def test_registry_rejects_empty_version():
    with pytest.raises(ValueError, match="registry version must not be empty"):
        VisualStrategyRegistry(version=" ", profiles=[_profile()], resources=_resources())


def test_source_scoped_requirements_are_preserved_without_flattening():
    profile = _profile(
        required_tags=[],
        required_tag_requirements=(
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.BUSINESS,
                all_of=["business_signal_alpha"],
            ),
            VisualStrategyTagRequirement(
                source=VisualStrategyContextSource.PRODUCT_VISUAL,
                all_of=["product_signal_beta"],
            ),
        ),
    )

    registry = VisualStrategyRegistry(version="v1", profiles=[profile], resources=_resources())
    stored = registry.get("strategy_alpha")

    assert stored.required_tags == frozenset()
    assert [requirement.source for requirement in stored.required_tag_requirements] == [
        VisualStrategyContextSource.BUSINESS,
        VisualStrategyContextSource.PRODUCT_VISUAL,
    ]


def test_default_resource_catalog_reads_actual_catalog_ids():
    resources = build_visual_strategy_resource_catalog()

    assert "generic_clean_ad_background" in resources.composition_template_ids
    assert "generic_clean_ad_background" in resources.mood_preset_ids
    assert "generic_v1" in resources.copy_tone_profile_ids
    assert resources.provider_capability_ids is None


def test_resource_catalog_rejects_non_string_copy_policy_id(monkeypatch):
    from orchestrator.app.llm import visual_strategy_registry

    monkeypatch.setitem(visual_strategy_registry.POLICIES, "broken", {"policy_id": 123})

    with pytest.raises(ValueError, match="copy tone policy ID must be a string"):
        build_visual_strategy_resource_catalog()


def test_default_visual_strategy_profiles_reference_actual_resources():
    resources = build_visual_strategy_resource_catalog()
    profiles = build_default_visual_strategy_profiles(resources)
    registry = build_default_visual_strategy_registry(resources=resources)

    assert profiles
    assert len({profile.strategy_id for profile in profiles}) == len(profiles)
    assert registry.list_profiles()
    for profile in registry.list_profiles(include_disabled=True):
        assert profile.composition_template_id in resources.composition_template_ids
        assert profile.mood_preset_id in resources.mood_preset_ids
        assert profile.copy_tone_profile_id in resources.copy_tone_profile_ids
        assert profile.supported_domains
        assert not (profile.required_tags & profile.excluded_tags)
        assert not (profile.preferred_tags & profile.excluded_tags)


def test_default_specialized_profiles_are_evidence_gated_or_disabled():
    registry = build_default_visual_strategy_registry()
    profiles = {profile.strategy_id: profile for profile in registry.list_profiles(include_disabled=True)}

    bbq = profiles["restaurant_bbq_warm_grill"]
    assert bbq.enabled is True
    assert [(item.source, item.all_of) for item in bbq.required_tag_requirements] == [
        (VisualStrategyContextSource.BUSINESS, frozenset({"korean_bbq"})),
        (VisualStrategyContextSource.PRODUCT_VISUAL_FACT, frozenset({"grilled_meat", "table_grilled"})),
    ]

    for sid in (
        "cafe_dessert_soft_premium",
        "restaurant_clean_food_hero",
        "beauty_skincare_clean_premium",
        "beauty_hair_salon_clean",
        "beauty_nail_clean_detail",
        "beauty_spa_soft_wellness",
    ):
        assert profiles[sid].enabled is False


def test_default_generic_profile_covers_all_canonical_domains():
    registry = build_default_visual_strategy_registry()
    generic = registry.get("generic_clean_ad_background")

    assert generic.supported_domains == frozenset(CanonicalBusinessDomain)


def test_tag_inventory_exposes_profile_tags_without_whitelist():
    registry = build_default_visual_strategy_registry()
    inventory = registry.tag_inventory(include_disabled=True)

    assert "restaurant_bbq_warm_grill" in inventory
    assert {"korean_bbq", "grilled_meat", "table_grilled", "grill", "smoke", "charcoal", "meat"}.issubset(inventory["restaurant_bbq_warm_grill"])
