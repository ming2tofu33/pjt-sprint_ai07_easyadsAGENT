"""Read-only registry for declarative visual strategy profiles."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from enum import Enum
from typing import Any

from pydantic import BaseModel

from orchestrator.app.llm.copy_tone_policy import POLICIES
from orchestrator.app.llm.visual_presets import get_visual_presets
from orchestrator.app.llm.visual_templates import get_visual_templates
from orchestrator.app.schemas.visual_strategy import VisualStrategyProfile, VisualStrategyResourceCatalog


def build_visual_strategy_resource_catalog(
    *,
    provider_capability_ids: Iterable[str] | None = None,
) -> VisualStrategyResourceCatalog:
    """Build a resource ID snapshot from existing read-only catalogs."""

    copy_tone_profile_ids: list[str] = []
    for policy in POLICIES.values():
        policy_id = policy["policy_id"]
        if not isinstance(policy_id, str):
            raise ValueError("copy tone policy ID must be a string")
        copy_tone_profile_ids.append(policy_id)

    return VisualStrategyResourceCatalog(
        composition_template_ids=frozenset(template.template_id for template in get_visual_templates()),
        mood_preset_ids=frozenset(get_visual_presets().keys()),
        copy_tone_profile_ids=frozenset(copy_tone_profile_ids),
        provider_capability_ids=None if provider_capability_ids is None else frozenset(provider_capability_ids),
    )


class VisualStrategyRegistry:
    """Immutable snapshot of visual strategy profiles and resource references."""

    def __init__(
        self,
        *,
        version: str,
        profiles: Iterable[VisualStrategyProfile],
        resources: VisualStrategyResourceCatalog,
    ) -> None:
        normalized_version = version.strip() if isinstance(version, str) else ""
        if not normalized_version:
            raise ValueError("registry version must not be empty")

        profile_list = tuple(profiles)
        profiles_by_id: dict[str, VisualStrategyProfile] = {}
        for profile in profile_list:
            sid = profile.strategy_id
            if sid in profiles_by_id:
                raise ValueError(f"duplicate visual strategy ID: {sid}")
            self._validate_resource_references(profile, resources)
            profiles_by_id[sid] = profile

        self._version = normalized_version
        self._resources = resources
        self._profiles_by_id = profiles_by_id
        self._profiles = tuple(sorted(profile_list, key=lambda item: (-item.priority, item.strategy_id)))
        self._snapshot_hash = self._build_snapshot_hash()

    @property
    def version(self) -> str:
        return self._version

    @property
    def snapshot_hash(self) -> str:
        return self._snapshot_hash

    def compute_snapshot_hash(self) -> str:
        return self._build_snapshot_hash()

    def get(self, strategy_id: str) -> VisualStrategyProfile:
        return self._profiles_by_id[strategy_id]

    def get_optional(self, strategy_id: str) -> VisualStrategyProfile | None:
        return self._profiles_by_id.get(strategy_id)

    def list_profiles(self, *, include_disabled: bool = False) -> tuple[VisualStrategyProfile, ...]:
        if include_disabled:
            return self._profiles
        return tuple(profile for profile in self._profiles if profile.enabled)

    def contains(self, strategy_id: str) -> bool:
        return strategy_id in self._profiles_by_id

    def tag_inventory(self, *, include_disabled: bool = False) -> dict[str, tuple[str, ...]]:
        profiles = self.list_profiles(include_disabled=include_disabled)
        return {
            profile.strategy_id: tuple(
                sorted(
                    profile.required_tags
                    | profile.preferred_tags
                    | profile.excluded_tags
                    | profile.introduced_visual_elements
                    | frozenset(
                        tag
                        for requirement in profile.required_tag_requirements
                        for tag in (requirement.all_of | requirement.any_of)
                    )
                    | frozenset(
                        tag
                        for element_requirement in profile.visual_element_evidence_requirements
                        for requirement in element_requirement.requirements
                        for tag in (requirement.all_of | requirement.any_of)
                    )
                )
            )
            for profile in profiles
        }

    @staticmethod
    def _validate_resource_references(profile: VisualStrategyProfile, resources: VisualStrategyResourceCatalog) -> None:
        if profile.composition_template_id not in resources.composition_template_ids:
            raise ValueError(f"unknown composition template ID: {profile.composition_template_id}")
        if profile.mood_preset_id not in resources.mood_preset_ids:
            raise ValueError(f"unknown mood preset ID: {profile.mood_preset_id}")
        if profile.copy_tone_profile_id not in resources.copy_tone_profile_ids:
            raise ValueError(f"unknown copy tone profile ID: {profile.copy_tone_profile_id}")
        if resources.provider_capability_ids is not None:
            missing = profile.provider_capabilities - resources.provider_capability_ids
            if missing:
                raise ValueError(f"unknown provider capability ID: {sorted(missing)[0]}")

    def _build_snapshot_hash(self) -> str:
        payload = {
            "version": self._version,
            "profiles": [_canonicalize(profile) for profile in sorted(self._profiles, key=lambda item: item.strategy_id)],
            "resources": _canonicalize(self._resources),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _canonicalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_canonicalize(item) for item in value),
            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False),
        )
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value
