"""Integrity validator for visual strategy registry snapshots."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Protocol

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry, build_visual_strategy_resource_catalog
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_integrity import (
    RegistryIntegrityPolicy,
    RegistryValidationCode,
    RegistryValidationIssue,
    RegistryValidationReport,
    RegistryValidationSeverity,
)


VISUAL_STRATEGY_REGISTRY_INTEGRITY_VALIDATOR_VERSION = "visual-strategy-registry-integrity-validator-v1"


class ResourceIdCatalog(Protocol):
    def list_ids(self) -> Iterable[str]:
        ...


PresetRegistryLike = ResourceIdCatalog | Iterable[str]
TemplateRegistryLike = ResourceIdCatalog | Iterable[str]
CopyToneRegistryLike = ResourceIdCatalog | Iterable[str]
ProviderCapabilityRegistryLike = ResourceIdCatalog | Iterable[str]


class VisualStrategyRegistryIntegrityError(ValueError):
    def __init__(self, report: RegistryValidationReport) -> None:
        self.report = report
        super().__init__(f"visual strategy registry integrity failed with {report.error_count} error(s)")


def assert_visual_strategy_registry_valid(report: RegistryValidationReport) -> None:
    if not report.valid:
        raise VisualStrategyRegistryIntegrityError(report)


def validate_visual_strategy_registry(
    registry: VisualStrategyRegistry,
    *,
    presets: PresetRegistryLike | None = None,
    templates: TemplateRegistryLike | None = None,
    copy_profiles: CopyToneRegistryLike | None = None,
    provider_capabilities: ProviderCapabilityRegistryLike | None = None,
    policy: RegistryIntegrityPolicy | None = None,
) -> RegistryValidationReport:
    resource_catalog = _resource_catalog_from_inputs(
        presets=presets,
        templates=templates,
        copy_profiles=copy_profiles,
        provider_capabilities=provider_capabilities,
    )
    report = validate_visual_strategy_profiles(
        registry.list_profiles(include_disabled=True),
        resources=resource_catalog,
        policy=policy,
        registry_version=registry.version,
        registry_snapshot_hash=registry.snapshot_hash,
        exposed_enabled_profiles=registry.list_profiles(),
    )
    return _with_hash_check(report, registry)


def validate_visual_strategy_profiles(
    profiles: Iterable[VisualStrategyProfile],
    *,
    resources: VisualStrategyResourceCatalog,
    policy: RegistryIntegrityPolicy | None = None,
    registry_version: str | None = None,
    registry_snapshot_hash: str | None = None,
    exposed_enabled_profiles: Iterable[VisualStrategyProfile] | None = None,
) -> RegistryValidationReport:
    validation_policy = policy or RegistryIntegrityPolicy()
    profile_list = tuple(profiles)
    issues: list[RegistryValidationIssue] = []

    issues.extend(_validate_duplicate_strategy_ids(profile_list))
    issues.extend(_validate_resources(profile_list, resources))
    issues.extend(_validate_archetypes(profile_list, validation_policy))
    issues.extend(_validate_profile_structure(profile_list, validation_policy))
    issues.extend(_validate_registry_shape(profile_list, validation_policy))
    if exposed_enabled_profiles is not None:
        issues.extend(_validate_exposed_profiles(exposed_enabled_profiles))

    issues = _sort_issues(issues)
    return _build_report(
        registry_version=registry_version,
        registry_snapshot_hash=registry_snapshot_hash,
        profiles=profile_list,
        resources=resources,
        policy=validation_policy,
        issues=issues,
    )


def _validate_duplicate_strategy_ids(profiles: tuple[VisualStrategyProfile, ...]) -> tuple[RegistryValidationIssue, ...]:
    counts = Counter(profile.strategy_id for profile in profiles)
    return tuple(
        _issue(
            code=RegistryValidationCode.DUPLICATE_STRATEGY_ID,
            severity=RegistryValidationSeverity.ERROR,
            strategy_id=strategy_id,
            field_path="strategy_id",
            message="strategy_id must be unique within a registry snapshot",
        )
        for strategy_id, count in counts.items()
        if count > 1
    )


def _validate_resources(
    profiles: tuple[VisualStrategyProfile, ...],
    resources: VisualStrategyResourceCatalog,
) -> tuple[RegistryValidationIssue, ...]:
    issues: list[RegistryValidationIssue] = []
    provider_ids = resources.provider_capability_ids
    if provider_ids is None:
        severity = RegistryValidationSeverity.WARNING
        issues.append(
            _issue(
                code=RegistryValidationCode.PROVIDER_CAPABILITY_CATALOG_UNAVAILABLE,
                severity=severity,
                field_path="provider_capabilities",
                message="provider capability catalog was not supplied",
            )
        )
    for profile in profiles:
        if profile.composition_template_id not in resources.composition_template_ids:
            issues.append(_missing_resource_issue(profile, RegistryValidationCode.MISSING_COMPOSITION_TEMPLATE, "composition_template_id", profile.composition_template_id))
        if profile.mood_preset_id not in resources.mood_preset_ids:
            issues.append(_missing_resource_issue(profile, RegistryValidationCode.MISSING_MOOD_PRESET, "mood_preset_id", profile.mood_preset_id))
        if profile.copy_tone_profile_id not in resources.copy_tone_profile_ids:
            issues.append(_missing_resource_issue(profile, RegistryValidationCode.MISSING_COPY_TONE_PROFILE, "copy_tone_profile_id", profile.copy_tone_profile_id))
        if provider_ids is not None:
            for capability in sorted(profile.provider_capabilities - provider_ids):
                issues.append(
                    _issue(
                        code=RegistryValidationCode.INVALID_PROVIDER_CAPABILITY,
                        severity=RegistryValidationSeverity.ERROR,
                        strategy_id=profile.strategy_id,
                        field_path="provider_capabilities",
                        related_id=capability,
                        message="provider capability must exist in the supplied catalog",
                    )
                )
    return tuple(issues)


def _validate_archetypes(
    profiles: tuple[VisualStrategyProfile, ...],
    policy: RegistryIntegrityPolicy,
) -> tuple[RegistryValidationIssue, ...]:
    if policy.allowed_archetypes is None:
        return ()
    return tuple(
        _issue(
            code=RegistryValidationCode.INVALID_ARCHETYPE,
            severity=RegistryValidationSeverity.ERROR,
            strategy_id=profile.strategy_id,
            field_path="archetype",
            related_id=profile.archetype,
            message="archetype must exist in the supplied archetype catalog",
        )
        for profile in profiles
        if profile.archetype not in policy.allowed_archetypes
    )


def _validate_profile_structure(
    profiles: tuple[VisualStrategyProfile, ...],
    policy: RegistryIntegrityPolicy,
) -> tuple[RegistryValidationIssue, ...]:
    issues: list[RegistryValidationIssue] = []
    for profile in profiles:
        issues.extend(_validate_tag_conflicts(profile))
        issues.extend(_validate_source_requirements(profile))
        issues.extend(_validate_visual_element_requirements(profile, policy))
    return tuple(issues)


def _validate_tag_conflicts(profile: VisualStrategyProfile) -> tuple[RegistryValidationIssue, ...]:
    checks = (
        (profile.required_tags & profile.excluded_tags, RegistryValidationCode.REQUIRED_EXCLUDED_TAG_CONFLICT, "required_tags"),
        (profile.preferred_tags & profile.excluded_tags, RegistryValidationCode.PREFERRED_EXCLUDED_TAG_CONFLICT, "preferred_tags"),
        (profile.required_tags & profile.preferred_tags, RegistryValidationCode.REQUIRED_PREFERRED_TAG_CONFLICT, "required_tags"),
    )
    return tuple(
        _issue(
            code=code,
            severity=RegistryValidationSeverity.ERROR,
            strategy_id=profile.strategy_id,
            field_path=field_path,
            related_id=tag,
            message="profile tag sets must not contain conflicting tags",
        )
        for tags, code, field_path in checks
        for tag in sorted(tags)
    )


def _validate_source_requirements(profile: VisualStrategyProfile) -> tuple[RegistryValidationIssue, ...]:
    counts = Counter(_requirement_key(requirement) for requirement in profile.required_tag_requirements)
    return tuple(
        _issue(
            code=RegistryValidationCode.DUPLICATE_SOURCE_REQUIREMENT,
            severity=RegistryValidationSeverity.ERROR,
            strategy_id=profile.strategy_id,
            field_path="required_tag_requirements",
            related_id=key,
            message="duplicate source requirement would duplicate scoring and trace entries",
        )
        for key, count in counts.items()
        if count > 1
    )


def _validate_visual_element_requirements(
    profile: VisualStrategyProfile,
    policy: RegistryIntegrityPolicy,
) -> tuple[RegistryValidationIssue, ...]:
    issues: list[RegistryValidationIssue] = []
    requirement_elements = tuple(requirement.element for requirement in profile.visual_element_evidence_requirements)
    counts = Counter(requirement_elements)
    for element, count in counts.items():
        if count > 1:
            issues.append(
                _issue(
                    code=RegistryValidationCode.DUPLICATE_VISUAL_ELEMENT_REQUIREMENT,
                    severity=RegistryValidationSeverity.ERROR,
                    strategy_id=profile.strategy_id,
                    field_path="visual_element_evidence_requirements",
                    related_id=element,
                    message="visual element evidence requirement must be unique per element",
                )
            )
    for element in sorted(set(requirement_elements) - set(profile.introduced_visual_elements)):
        issues.append(
            _issue(
                code=RegistryValidationCode.INTRODUCED_ELEMENT_WITHOUT_REQUIREMENT,
                severity=RegistryValidationSeverity.ERROR,
                strategy_id=profile.strategy_id,
                field_path="visual_element_evidence_requirements",
                related_id=element,
                message="visual element requirement references an element not introduced by the profile",
            )
        )
    if policy.require_all_introduced_elements_grounded:
        for element in sorted(set(profile.introduced_visual_elements) - set(requirement_elements)):
            issues.append(
                _issue(
                    code=RegistryValidationCode.INTRODUCED_ELEMENT_WITHOUT_REQUIREMENT,
                    severity=RegistryValidationSeverity.ERROR,
                    strategy_id=profile.strategy_id,
                    field_path="introduced_visual_elements",
                    related_id=element,
                    message="introduced visual element must have an evidence requirement",
                )
            )
    for index, element_requirement in enumerate(profile.visual_element_evidence_requirements):
        if not element_requirement.requirements:
            issues.append(
                _issue(
                    code=RegistryValidationCode.INTRODUCED_ELEMENT_WITHOUT_REQUIREMENT,
                    severity=RegistryValidationSeverity.ERROR,
                    strategy_id=profile.strategy_id,
                    field_path=f"visual_element_evidence_requirements.{index}.requirements",
                    related_id=element_requirement.element,
                    message="visual element requirement must contain at least one source requirement",
                )
            )
    return tuple(issues)


def _validate_registry_shape(
    profiles: tuple[VisualStrategyProfile, ...],
    policy: RegistryIntegrityPolicy,
) -> tuple[RegistryValidationIssue, ...]:
    issues: list[RegistryValidationIssue] = []
    enabled = tuple(profile for profile in profiles if profile.enabled)
    enabled_fallback = tuple(profile for profile in enabled if profile.fallback_tier > 0)
    if profiles and not enabled:
        issues.append(
            _issue(
                code=RegistryValidationCode.EMPTY_ENABLED_REGISTRY,
                severity=RegistryValidationSeverity.ERROR,
                message="registry must expose at least one enabled profile",
            )
        )
    if policy.require_enabled_fallback and not enabled_fallback:
        issues.append(
            _issue(
                code=RegistryValidationCode.MISSING_ENABLED_FALLBACK,
                severity=RegistryValidationSeverity.ERROR,
                field_path="fallback_tier",
                message="registry must include at least one enabled fallback profile",
            )
        )
    if policy.require_fallback_domain_coverage:
        for domain in CanonicalBusinessDomain:
            if not any(domain in profile.supported_domains for profile in enabled_fallback):
                issues.append(
                    _issue(
                        code=RegistryValidationCode.FALLBACK_WITHOUT_DOMAIN_COVERAGE,
                        severity=RegistryValidationSeverity.ERROR,
                        field_path="supported_domains",
                        related_id=domain.value,
                        message="enabled fallback profiles must cover every canonical business domain",
                    )
                )
    return tuple(issues)


def _validate_exposed_profiles(profiles: Iterable[VisualStrategyProfile]) -> tuple[RegistryValidationIssue, ...]:
    return tuple(
        _issue(
            code=RegistryValidationCode.DISABLED_PROFILE_EXPOSED,
            severity=RegistryValidationSeverity.ERROR,
            strategy_id=profile.strategy_id,
            field_path="enabled",
            message="registry default listing must not expose disabled profiles",
        )
        for profile in profiles
        if not profile.enabled
    )


def _with_hash_check(report: RegistryValidationReport, registry: VisualStrategyRegistry) -> RegistryValidationReport:
    build_hash = getattr(registry, "_build_snapshot_hash", None)
    if not callable(build_hash) or build_hash() == registry.snapshot_hash:
        return report
    issues = _sort_issues(
        [
            *report.issues,
            _issue(
                code=RegistryValidationCode.REGISTRY_HASH_MISMATCH,
                severity=RegistryValidationSeverity.ERROR,
                field_path="snapshot_hash",
                message="registry snapshot hash does not match canonical snapshot",
            ),
        ]
    )
    return _build_report(
        registry_version=report.registry_version,
        registry_snapshot_hash=report.registry_snapshot_hash,
        profiles=registry.list_profiles(include_disabled=True),
        resources=_resource_catalog_from_inputs(),
        policy=RegistryIntegrityPolicy(),
        issues=issues,
    )


def _build_report(
    *,
    registry_version: str | None,
    registry_snapshot_hash: str | None,
    profiles: tuple[VisualStrategyProfile, ...],
    resources: VisualStrategyResourceCatalog,
    policy: RegistryIntegrityPolicy,
    issues: list[RegistryValidationIssue],
) -> RegistryValidationReport:
    error_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.ERROR)
    warning_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.WARNING)
    info_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.INFO)
    provider_catalog_available = resources.provider_capability_ids is not None
    provider_catalog_required = policy.require_provider_capability_catalog
    if provider_catalog_required and not provider_catalog_available:
        replacement: list[RegistryValidationIssue] = []
        for issue in issues:
            if issue.code == RegistryValidationCode.PROVIDER_CAPABILITY_CATALOG_UNAVAILABLE:
                replacement.append(issue.model_copy(update={"severity": RegistryValidationSeverity.ERROR}))
            else:
                replacement.append(issue)
        issues = replacement
        error_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.ERROR)
        warning_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.WARNING)
        info_count = sum(1 for issue in issues if issue.severity == RegistryValidationSeverity.INFO)

    return RegistryValidationReport(
        validator_version=VISUAL_STRATEGY_REGISTRY_INTEGRITY_VALIDATOR_VERSION,
        registry_version=registry_version,
        registry_snapshot_hash=registry_snapshot_hash,
        profile_count=len(profiles),
        enabled_profile_count=sum(1 for profile in profiles if profile.enabled),
        disabled_profile_count=sum(1 for profile in profiles if not profile.enabled),
        fallback_profile_count=sum(1 for profile in profiles if profile.fallback_tier > 0),
        enabled_fallback_profile_count=sum(1 for profile in profiles if profile.enabled and profile.fallback_tier > 0),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        valid=error_count == 0,
        complete=provider_catalog_available and not provider_catalog_required or provider_catalog_available,
        issues=tuple(issues),
        checked_composition_template_count=len(resources.composition_template_ids),
        checked_mood_preset_count=len(resources.mood_preset_ids),
        checked_copy_tone_profile_count=len(resources.copy_tone_profile_ids),
        checked_provider_capability_count=0 if resources.provider_capability_ids is None else len(resources.provider_capability_ids),
        archetype_validation_mode="catalog" if policy.allowed_archetypes is not None else "open",
        provider_capability_validation_mode="catalog" if resources.provider_capability_ids is not None else "unavailable",
        discriminated_union_status="not_applied_no_structural_difference",
    )


def _resource_catalog_from_inputs(
    *,
    presets: PresetRegistryLike | None = None,
    templates: TemplateRegistryLike | None = None,
    copy_profiles: CopyToneRegistryLike | None = None,
    provider_capabilities: ProviderCapabilityRegistryLike | None = None,
) -> VisualStrategyResourceCatalog:
    default = build_visual_strategy_resource_catalog()
    return VisualStrategyResourceCatalog(
        composition_template_ids=_catalog_ids(templates) if templates is not None else default.composition_template_ids,
        mood_preset_ids=_catalog_ids(presets) if presets is not None else default.mood_preset_ids,
        copy_tone_profile_ids=_catalog_ids(copy_profiles) if copy_profiles is not None else default.copy_tone_profile_ids,
        provider_capability_ids=None if provider_capabilities is None else _catalog_ids(provider_capabilities),
    )


def _catalog_ids(catalog: ResourceIdCatalog | Iterable[str]) -> frozenset[str]:
    if hasattr(catalog, "list_ids"):
        return frozenset(catalog.list_ids())
    if isinstance(catalog, dict):
        return frozenset(catalog.keys())
    return frozenset(catalog)


def _missing_resource_issue(
    profile: VisualStrategyProfile,
    code: RegistryValidationCode,
    field_path: str,
    related_id: str,
) -> RegistryValidationIssue:
    return _issue(
        code=code,
        severity=RegistryValidationSeverity.ERROR,
        strategy_id=profile.strategy_id,
        field_path=field_path,
        related_id=related_id,
        message="profile resource reference must exist in the supplied catalog",
    )


def _issue(
    *,
    code: RegistryValidationCode,
    severity: RegistryValidationSeverity,
    message: str,
    strategy_id: str | None = None,
    field_path: str | None = None,
    related_id: str | None = None,
) -> RegistryValidationIssue:
    return RegistryValidationIssue(
        code=code,
        severity=severity,
        strategy_id=strategy_id,
        field_path=field_path,
        related_id=related_id,
        message=message,
    )


def _sort_issues(issues: Iterable[RegistryValidationIssue]) -> list[RegistryValidationIssue]:
    severity_order = {
        RegistryValidationSeverity.ERROR: 0,
        RegistryValidationSeverity.WARNING: 1,
        RegistryValidationSeverity.INFO: 2,
    }
    return sorted(
        issues,
        key=lambda issue: (
            severity_order[issue.severity],
            issue.code.value,
            issue.strategy_id or "",
            issue.field_path or "",
            issue.related_id or "",
        ),
    )


def _requirement_key(requirement: VisualStrategyTagRequirement) -> str:
    return "|".join(
        (
            requirement.source.value,
            ",".join(sorted(requirement.all_of)),
            ",".join(sorted(requirement.any_of)),
        )
    )
