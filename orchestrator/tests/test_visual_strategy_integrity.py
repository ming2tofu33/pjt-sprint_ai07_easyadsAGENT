from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.app.llm.domain_routing import CanonicalBusinessDomain
from orchestrator.app.llm.visual_strategy_integrity import (
    VISUAL_STRATEGY_REGISTRY_INTEGRITY_VALIDATOR_VERSION,
    VisualStrategyRegistryIntegrityError,
    assert_visual_strategy_registry_valid,
    build_default_visual_strategy_integrity_policy,
    validate_visual_strategy_profiles,
    validate_visual_strategy_registry,
)
from orchestrator.app.llm.visual_strategy_profiles import build_default_visual_strategy_registry
from orchestrator.app.llm.visual_strategy_registry import VisualStrategyRegistry
from orchestrator.app.schemas.visual_strategy import (
    VisualElementEvidenceRequirement,
    VisualStrategyContextSource,
    VisualStrategyProfile,
    VisualStrategyResourceCatalog,
    VisualStrategyTagRequirement,
)
from orchestrator.app.schemas.visual_strategy_integrity import (
    DiscriminatedUnionAuditStatus,
    RegistryIntegrityPolicy,
    RegistryValidationCode,
    RegistryValidationIssue,
    RegistryValidationReport,
    RegistryValidationSeverity,
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
        "archetype": "open_archetype",
        "supported_domains": [CanonicalBusinessDomain.RETAIL],
        "composition_template_id": "template_alpha",
        "mood_preset_id": "preset_alpha",
        "copy_tone_profile_id": "tone_alpha",
        "priority": 10,
        "fallback_tier": 1,
        "fallback_role": "fallback_role_alpha",
        "enabled": True,
    }
    data.update(overrides)
    return VisualStrategyProfile(**data)


def _issue(code: RegistryValidationCode, severity: RegistryValidationSeverity) -> RegistryValidationIssue:
    return RegistryValidationIssue(code=code, severity=severity, message="issue")


def test_integrity_schema_contract_fields_and_invariants():
    assert set(RegistryValidationIssue.model_fields) == {
        "code",
        "severity",
        "strategy_id",
        "field_path",
        "related_id",
        "message",
    }
    assert set(RegistryValidationReport.model_fields) == {
        "validator_version",
        "registry_version",
        "registry_snapshot_hash",
        "profile_count",
        "enabled_profile_count",
        "disabled_profile_count",
        "fallback_profile_count",
        "enabled_fallback_profile_count",
        "error_count",
        "warning_count",
        "info_count",
        "valid",
        "complete",
        "issues",
        "checked_composition_template_count",
        "checked_mood_preset_count",
        "checked_copy_tone_profile_count",
        "checked_provider_capability_count",
        "archetype_validation_mode",
        "provider_capability_validation_mode",
        "snapshot_hash_validation_mode",
        "discriminated_union_status",
    }
    with pytest.raises(ValidationError):
        RegistryValidationIssue(code=RegistryValidationCode.EMPTY_ENABLED_REGISTRY, severity=RegistryValidationSeverity.ERROR, message="issue", extra=True)
    issue = _issue(RegistryValidationCode.EMPTY_ENABLED_REGISTRY, RegistryValidationSeverity.ERROR)
    with pytest.raises(ValidationError):
        RegistryValidationReport(
            validator_version="validator",
            registry_version=None,
            registry_snapshot_hash=None,
            profile_count=1,
            enabled_profile_count=1,
            disabled_profile_count=0,
            fallback_profile_count=1,
            enabled_fallback_profile_count=1,
            error_count=0,
            warning_count=0,
            info_count=0,
            valid=True,
            complete=True,
            issues=(issue,),
            checked_composition_template_count=1,
            checked_mood_preset_count=1,
            checked_copy_tone_profile_count=1,
            checked_provider_capability_count=0,
            archetype_validation_mode="open",
            provider_capability_validation_mode="unavailable",
            snapshot_hash_validation_mode="unavailable",
            discriminated_union_status=DiscriminatedUnionAuditStatus.NOT_EVALUATED,
        )


def test_issue_codes_and_severities_are_contract_enums():
    assert RegistryValidationSeverity.ERROR.value == "error"
    assert RegistryValidationCode.DUPLICATE_STRATEGY_ID.value == "duplicate_strategy_id"
    assert RegistryValidationCode.REGISTRY_HASH_MISMATCH.value == "registry_hash_mismatch"
    assert RegistryValidationCode.VISUAL_ELEMENT_REQUIREMENT_WITHOUT_INTRODUCED_ELEMENT.value == "visual_element_requirement_without_introduced_element"
    assert RegistryValidationCode.MISSING_REQUIRED_FALLBACK_ROLE.value == "missing_required_fallback_role"


def test_raw_profile_validation_collects_duplicate_ids_and_missing_resources():
    report = validate_visual_strategy_profiles(
        [
            _profile(strategy_id="duplicate", composition_template_id="missing_template"),
            _profile(strategy_id="duplicate", mood_preset_id="missing_preset", copy_tone_profile_id="missing_tone"),
        ],
        resources=_resources(provider_capability_ids=[]),
    )

    assert report.valid is False
    assert {
        RegistryValidationCode.DUPLICATE_STRATEGY_ID,
        RegistryValidationCode.MISSING_COMPOSITION_TEMPLATE,
        RegistryValidationCode.MISSING_MOOD_PRESET,
        RegistryValidationCode.MISSING_COPY_TONE_PROFILE,
    }.issubset({issue.code for issue in report.issues})
    assert [issue.severity for issue in report.issues] == sorted(issue.severity for issue in report.issues)


def test_raw_profile_validation_collects_defensive_profile_structure_issues():
    requirement = VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["local"])
    valid_profile = _profile(
        required_tag_requirements=(requirement, requirement),
        introduced_visual_elements=["hero_prop", "ungrounded"],
        visual_element_evidence_requirements=(
            VisualElementEvidenceRequirement(element="hero_prop", requirements=(requirement,)),
        ),
    )
    duplicate_requirement = VisualElementEvidenceRequirement(element="hero_prop", requirements=(requirement,))
    raw_profile_data = {field_name: getattr(valid_profile, field_name) for field_name in VisualStrategyProfile.model_fields}
    profile = VisualStrategyProfile.model_construct(
        **{
            **raw_profile_data,
            "required_tags": frozenset({"conflict"}),
            "preferred_tags": frozenset({"conflict"}),
            "excluded_tags": frozenset({"conflict"}),
            "visual_element_evidence_requirements": (duplicate_requirement, duplicate_requirement),
        }
    )

    report = validate_visual_strategy_profiles([profile], resources=_resources(provider_capability_ids=[]))

    codes = {issue.code for issue in report.issues}
    assert RegistryValidationCode.REQUIRED_EXCLUDED_TAG_CONFLICT in codes
    assert RegistryValidationCode.PREFERRED_EXCLUDED_TAG_CONFLICT in codes
    assert RegistryValidationCode.REQUIRED_PREFERRED_TAG_CONFLICT in codes
    assert RegistryValidationCode.DUPLICATE_SOURCE_REQUIREMENT in codes
    assert RegistryValidationCode.DUPLICATE_VISUAL_ELEMENT_REQUIREMENT in codes
    assert RegistryValidationCode.INTRODUCED_ELEMENT_WITHOUT_REQUIREMENT in codes


def test_delimiter_characters_do_not_create_false_duplicate_source_requirements():
    requirements = (
        VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["alpha,beta"]),
        VisualStrategyTagRequirement(source=VisualStrategyContextSource.BUSINESS, all_of=["alpha", "beta"]),
    )

    report = validate_visual_strategy_profiles(
        [_profile(required_tag_requirements=requirements)],
        resources=_resources(provider_capability_ids=[]),
    )

    assert RegistryValidationCode.DUPLICATE_SOURCE_REQUIREMENT not in {issue.code for issue in report.issues}


def test_visual_element_inner_duplicate_source_requirement_is_reported():
    requirement = VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["visible"])
    profile = _profile(
        introduced_visual_elements=["hero_prop"],
        visual_element_evidence_requirements=(
            VisualElementEvidenceRequirement(element="hero_prop", requirements=(requirement, requirement)),
        ),
    )

    report = validate_visual_strategy_profiles([profile], resources=_resources(provider_capability_ids=[]))

    assert any(
        issue.code == RegistryValidationCode.DUPLICATE_SOURCE_REQUIREMENT
        and issue.field_path == "visual_element_evidence_requirements.0.requirements"
        for issue in report.issues
    )


def test_visual_element_requirement_without_introduced_element_uses_specific_code():
    requirement = VisualStrategyTagRequirement(source=VisualStrategyContextSource.PRODUCT_VISUAL_FACT, all_of=["visible"])
    valid_profile = _profile()
    raw_profile_data = {field_name: getattr(valid_profile, field_name) for field_name in VisualStrategyProfile.model_fields}
    profile = VisualStrategyProfile.model_construct(
        **{
            **raw_profile_data,
            "introduced_visual_elements": frozenset(),
            "visual_element_evidence_requirements": (
                VisualElementEvidenceRequirement(element="hero_prop", requirements=(requirement,)),
            ),
        }
    )

    report = validate_visual_strategy_profiles([profile], resources=_resources(provider_capability_ids=[]))

    assert RegistryValidationCode.VISUAL_ELEMENT_REQUIREMENT_WITHOUT_INTRODUCED_ELEMENT in {issue.code for issue in report.issues}


def test_raw_profile_validation_reports_provider_catalog_modes():
    profile = _profile(provider_capabilities=["capability_alpha"])

    warning_report = validate_visual_strategy_profiles([profile], resources=_resources(provider_capability_ids=None))
    assert warning_report.valid is True
    assert warning_report.complete is False
    assert warning_report.provider_capability_validation_mode == "unavailable"
    assert warning_report.issues[0].code == RegistryValidationCode.PROVIDER_CAPABILITY_CATALOG_UNAVAILABLE
    assert warning_report.issues[0].severity == RegistryValidationSeverity.WARNING

    required_report = validate_visual_strategy_profiles(
        [profile],
        resources=_resources(provider_capability_ids=None),
        policy=RegistryIntegrityPolicy(require_provider_capability_catalog=True),
    )
    assert required_report.valid is False
    assert required_report.issues[0].severity == RegistryValidationSeverity.ERROR

    invalid_report = validate_visual_strategy_profiles([profile], resources=_resources(provider_capability_ids=["capability_beta"]))
    assert RegistryValidationCode.INVALID_PROVIDER_CAPABILITY in {issue.code for issue in invalid_report.issues}


def test_provider_catalog_is_not_required_when_profiles_do_not_need_capabilities():
    report = validate_visual_strategy_profiles([_profile()], resources=_resources(provider_capability_ids=None))

    assert report.valid is True
    assert report.complete is True
    assert report.warning_count == 0
    assert report.provider_capability_validation_mode == "not_required"


def test_provider_warning_promoted_to_error_is_resorted_deterministically():
    report = validate_visual_strategy_profiles(
        [_profile(composition_template_id="missing", provider_capabilities=["capability_alpha"])],
        resources=_resources(provider_capability_ids=None),
        policy=RegistryIntegrityPolicy(require_provider_capability_catalog=True),
    )

    assert [issue.severity for issue in report.issues] == [RegistryValidationSeverity.ERROR, RegistryValidationSeverity.ERROR]
    assert [issue.code for issue in report.issues] == sorted(issue.code for issue in report.issues)


def test_fallback_checks_use_tier_not_strategy_id_text():
    no_fallback = _profile(strategy_id="fallback_named_but_primary", fallback_tier=0, fallback_role=None)
    report = validate_visual_strategy_profiles([no_fallback], resources=_resources(provider_capability_ids=[]))

    assert RegistryValidationCode.MISSING_ENABLED_FALLBACK in {issue.code for issue in report.issues}


def test_optional_fallback_domain_coverage_checks_enum_values():
    report = validate_visual_strategy_profiles(
        [_profile(supported_domains=[CanonicalBusinessDomain.RETAIL])],
        resources=_resources(provider_capability_ids=[]),
        policy=RegistryIntegrityPolicy(require_fallback_domain_coverage=True),
    )

    missing_domains = {issue.related_id for issue in report.issues if issue.code == RegistryValidationCode.FALLBACK_WITHOUT_DOMAIN_COVERAGE}
    assert CanonicalBusinessDomain.FOOD_AND_BEVERAGE.value in missing_domains


def test_empty_enabled_registry_and_disabled_exposure_are_reported():
    disabled = _profile(enabled=False)
    report = validate_visual_strategy_profiles([disabled], resources=_resources(provider_capability_ids=[]))

    assert RegistryValidationCode.EMPTY_ENABLED_REGISTRY in {issue.code for issue in report.issues}
    assert RegistryValidationCode.MISSING_ENABLED_FALLBACK in {issue.code for issue in report.issues}

    exposed = validate_visual_strategy_profiles([disabled], resources=_resources(provider_capability_ids=[]), exposed_enabled_profiles=[disabled])
    assert RegistryValidationCode.DISABLED_PROFILE_EXPOSED in {issue.code for issue in exposed.issues}


def test_empty_profile_list_reports_empty_enabled_registry_and_missing_fallback():
    report = validate_visual_strategy_profiles([], resources=_resources(provider_capability_ids=[]))

    assert RegistryValidationCode.EMPTY_ENABLED_REGISTRY in {issue.code for issue in report.issues}
    assert RegistryValidationCode.MISSING_ENABLED_FALLBACK in {issue.code for issue in report.issues}


def test_required_fallback_role_policy_reports_missing_or_disabled_roles():
    disabled = _profile(enabled=False)
    report = validate_visual_strategy_profiles(
        [disabled],
        resources=_resources(provider_capability_ids=[]),
        policy=RegistryIntegrityPolicy(required_fallback_roles=frozenset({"fallback_role_alpha"})),
    )

    assert RegistryValidationCode.MISSING_REQUIRED_FALLBACK_ROLE in {issue.code for issue in report.issues}


def test_fallback_role_shape_issues_are_reported_defensively():
    fallback_without_role = _profile().model_copy(update={"fallback_role": None})
    primary_with_role = _profile(fallback_tier=0, fallback_role=None).model_copy(update={"fallback_role": "fallback_role_alpha"})

    report = validate_visual_strategy_profiles(
        [fallback_without_role, primary_with_role],
        resources=_resources(provider_capability_ids=[]),
    )

    assert RegistryValidationCode.FALLBACK_PROFILE_MISSING_ROLE in {issue.code for issue in report.issues}
    assert RegistryValidationCode.PRIMARY_PROFILE_HAS_FALLBACK_ROLE in {issue.code for issue in report.issues}


def test_archetype_open_and_catalog_modes():
    open_report = validate_visual_strategy_profiles([_profile(archetype="new_archetype")], resources=_resources(provider_capability_ids=[]))
    assert open_report.valid is True
    assert open_report.archetype_validation_mode == "open"

    catalog_report = validate_visual_strategy_profiles(
        [_profile(archetype="new_archetype")],
        resources=_resources(provider_capability_ids=[]),
        policy=RegistryIntegrityPolicy(allowed_archetypes=frozenset({"known_archetype"})),
    )
    assert catalog_report.valid is False
    assert RegistryValidationCode.INVALID_ARCHETYPE in {issue.code for issue in catalog_report.issues}
    assert catalog_report.archetype_validation_mode == "catalog"


def test_policy_rejects_single_string_archetype_catalog_and_non_bool_flags():
    assert RegistryIntegrityPolicy().version == "visual-strategy-registry-integrity-policy-v2"
    assert build_default_visual_strategy_integrity_policy().version == "visual-strategy-registry-integrity-policy-v2"
    assert build_default_visual_strategy_integrity_policy().required_fallback_roles == frozenset(
        {
            "product_editorial",
            "service_lifestyle",
            "local_business",
            "information_poster",
            "brand_awareness",
        }
    )
    with pytest.raises(ValidationError):
        RegistryIntegrityPolicy(allowed_archetypes="poster")
    with pytest.raises(ValidationError):
        RegistryIntegrityPolicy(require_enabled_fallback=1)


def test_built_registry_validation_uses_supplied_catalogs_and_public_enabled_listing():
    profile = _profile(provider_capabilities=["capability_alpha"])
    registry = VisualStrategyRegistry(version="v1", profiles=[profile], resources=_resources(provider_capability_ids=["capability_alpha"]))

    report = validate_visual_strategy_registry(
        registry,
        templates=["template_alpha"],
        presets=["preset_alpha"],
        copy_profiles=["tone_alpha"],
        provider_capabilities=["capability_alpha"],
    )

    assert report.valid is True
    assert report.complete is True
    assert report.registry_version == "v1"
    assert report.registry_snapshot_hash == registry.snapshot_hash
    assert report.checked_provider_capability_count == 1
    assert report.snapshot_hash_validation_mode == "verified"


def test_hash_mismatch_preserves_original_catalog_and_policy_context():
    profile = _profile(provider_capabilities=["capability_alpha"])
    registry = VisualStrategyRegistry(version="v1", profiles=[profile], resources=_resources(provider_capability_ids=["capability_alpha"]))
    registry._snapshot_hash = "tampered"

    report = validate_visual_strategy_registry(
        registry,
        templates=["template_alpha"],
        presets=["preset_alpha"],
        copy_profiles=["tone_alpha"],
        provider_capabilities=["capability_alpha"],
        policy=RegistryIntegrityPolicy(
            allowed_archetypes=frozenset({"open_archetype"}),
            require_fallback_domain_coverage=True,
            discriminated_union_status=DiscriminatedUnionAuditStatus.NOT_APPLIED_NO_STRUCTURAL_DIFFERENCE,
        ),
    )

    assert RegistryValidationCode.REGISTRY_HASH_MISMATCH in {issue.code for issue in report.issues}
    assert report.valid is False
    assert report.checked_provider_capability_count == 1
    assert report.provider_capability_validation_mode == "catalog"
    assert report.archetype_validation_mode == "catalog"
    assert report.discriminated_union_status == DiscriminatedUnionAuditStatus.NOT_APPLIED_NO_STRUCTURAL_DIFFERENCE
    assert RegistryValidationCode.FALLBACK_WITHOUT_DOMAIN_COVERAGE in {issue.code for issue in report.issues}


def test_hash_validation_mode_is_unavailable_without_public_hash_helper():
    class RegistryWithoutHashHelper:
        version = "v1"
        snapshot_hash = "hash"

        def __init__(self, profile: VisualStrategyProfile) -> None:
            self.profile = profile

        def list_profiles(self, *, include_disabled: bool = False):
            return (self.profile,)

    report = validate_visual_strategy_registry(
        RegistryWithoutHashHelper(_profile()),
        templates=["template_alpha"],
        presets=["preset_alpha"],
        copy_profiles=["tone_alpha"],
        provider_capabilities=[],
    )

    assert report.snapshot_hash_validation_mode == "unavailable"
    assert RegistryValidationCode.REGISTRY_HASH_MISMATCH not in {issue.code for issue in report.issues}


def test_catalog_inputs_reject_single_strings_and_non_string_ids():
    registry = VisualStrategyRegistry(version="v1", profiles=[_profile()], resources=_resources())

    with pytest.raises(TypeError):
        validate_visual_strategy_registry(registry, templates="template_alpha")
    with pytest.raises(TypeError):
        validate_visual_strategy_registry(registry, templates=[object()])


def test_default_registry_validation_report_is_valid_and_complete_when_provider_catalog_is_not_needed():
    registry = build_default_visual_strategy_registry()
    report = validate_visual_strategy_registry(registry, policy=build_default_visual_strategy_integrity_policy())

    assert report.validator_version == VISUAL_STRATEGY_REGISTRY_INTEGRITY_VALIDATOR_VERSION
    assert report.valid is True
    assert report.complete is True
    assert report.error_count == 0
    assert report.warning_count == 0
    assert report.profile_count == len(registry.list_profiles(include_disabled=True))
    assert report.enabled_fallback_profile_count >= 5
    assert RegistryValidationCode.MISSING_REQUIRED_FALLBACK_ROLE not in {issue.code for issue in report.issues}
    assert report.provider_capability_validation_mode == "not_required"
    assert report.discriminated_union_status == DiscriminatedUnionAuditStatus.NOT_EVALUATED


def test_report_rejects_negative_and_inconsistent_counts():
    payload = {
        "validator_version": "validator",
        "registry_version": None,
        "registry_snapshot_hash": None,
        "profile_count": 1,
        "enabled_profile_count": 1,
        "disabled_profile_count": 0,
        "fallback_profile_count": 1,
        "enabled_fallback_profile_count": 1,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "valid": True,
        "complete": True,
        "issues": (),
        "checked_composition_template_count": 1,
        "checked_mood_preset_count": 1,
        "checked_copy_tone_profile_count": 1,
        "checked_provider_capability_count": 0,
        "archetype_validation_mode": "open",
        "provider_capability_validation_mode": "not_required",
        "snapshot_hash_validation_mode": "unavailable",
        "discriminated_union_status": DiscriminatedUnionAuditStatus.NOT_EVALUATED,
    }
    with pytest.raises(ValidationError):
        RegistryValidationReport(**{**payload, "profile_count": -1})
    with pytest.raises(ValidationError):
        RegistryValidationReport(**{**payload, "fallback_profile_count": 2})


def test_integrity_error_helper_raises_only_for_invalid_report():
    valid_report = validate_visual_strategy_profiles([_profile()], resources=_resources(provider_capability_ids=[]))
    assert_visual_strategy_registry_valid(valid_report)

    invalid_report = validate_visual_strategy_profiles([_profile(composition_template_id="missing")], resources=_resources(provider_capability_ids=[]))
    with pytest.raises(VisualStrategyRegistryIntegrityError) as exc:
        assert_visual_strategy_registry_valid(invalid_report)
    assert exc.value.report is invalid_report
