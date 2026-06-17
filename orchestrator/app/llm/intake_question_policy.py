"""Deterministic question policy for intake-time clarifications."""

from __future__ import annotations

from collections.abc import Sequence

from orchestrator.app.llm.campaign_semantics import (
    campaign_intent_subject_requirement,
    is_business_level_campaign_intent,
    is_item_level_campaign_intent,
)
from orchestrator.app.llm.campaign_context_service import build_campaign_context
from orchestrator.app.llm.domain_routing import DomainSupportStatus, normalize_business_type
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.input_evidence import InputConflict
from orchestrator.app.schemas.intake_question_policy import (
    FieldRequirementDecision,
    IntakeQuestionPolicyConfig,
    IntakeQuestionPolicyDecision,
)
from orchestrator.app.schemas.intake_understanding import IntakeUnderstandingResult
from orchestrator.app.schemas.llm_marketing import MarketingContext


POLICY_VERSION = "advertised_subject_campaign_aware_v1"
PRODUCT_OR_SERVICE_TYPES = frozenset({"product", "service"})
BUSINESS_SUBJECT_TYPES = frozenset({"business", "brand", "venue"})
QUESTION_POLICY_FIELDS = ("business_type", "item_or_service", "promotion_goal", "ad_format")
AMBIGUITY_FIELD_MAP = {
    "beauty_subtype_ambiguous": {"business_type"},
    "campaign_intent_ambiguous": {"promotion_goal"},
    "subject_type_ambiguous": {"item_or_service"},
}


def campaign_context_from_intake_understanding(
    intake: IntakeUnderstandingResult,
    context: MarketingContext,
) -> CampaignContext:
    evidence_refs = [
        item.evidence_id
        for item in intake.evidence_items
        if item.key in {"campaign_intent_candidate", "tone_candidates"}
    ]
    confidence = max(
        float(intake.confidence_by_field.get("campaign_intent_candidate") or 0.0),
        float(intake.confidence_by_field.get("promotion_goal") or 0.0),
        0.0,
    )
    if not evidence_refs:
        return CampaignContext(confidence=confidence)
    return build_campaign_context(
        campaign_intent=intake.campaign_intent_candidate,
        promotion_goal=context.promotion_goal,
        desired_positioning=intake.tone_candidates,
        evidence_refs=evidence_refs,
        confidence=confidence,
    )


def is_intake_routeable(
    domain_routing,
    *,
    advertised_subject: str | None,
    product_or_service: str | None,
    ad_format: str | None,
    blocking_conflicts: Sequence[InputConflict],
) -> bool:
    if not ad_format or blocking_conflicts:
        return False
    if not advertised_subject and not product_or_service:
        return False
    return domain_routing.support_status in {
        DomainSupportStatus.SPECIALIZED,
        DomainSupportStatus.GENERIC_FALLBACK,
    }


def resolve_intake_question_policy(
    *,
    context: MarketingContext,
    intake: IntakeUnderstandingResult,
    campaign: CampaignContext,
    requested_ad_format: str | None,
    input_conflicts: Sequence[InputConflict],
    confirmed_fields: Sequence[str] = (),
    policy: IntakeQuestionPolicyConfig | None = None,
) -> IntakeQuestionPolicyDecision:
    policy = policy or IntakeQuestionPolicyConfig()
    blocking_conflicts = tuple(
        conflict
        for conflict in input_conflicts
        if conflict.severity in policy.blocking_conflict_severities
    )
    blocking_conflict_fields = tuple(f"{conflict.field}:{conflict.severity}" for conflict in blocking_conflicts)
    confirmed_field_set = {field for field in confirmed_fields if field}
    blocking_ambiguities = tuple(
        flag
        for flag in intake.ambiguity_flags
        if any(field not in confirmed_field_set for field in AMBIGUITY_FIELD_MAP.get(flag, set()))
    )
    ad_format = requested_ad_format or context.extra.get("ad_format") or intake.ad_format_candidate
    domain_routing = normalize_business_type(context.business_type)
    routeable = is_intake_routeable(
        domain_routing,
        advertised_subject=intake.advertised_subject,
        product_or_service=context.item_or_service or intake.product_or_service_candidate,
        ad_format=ad_format,
        blocking_conflicts=blocking_conflicts,
    )

    decisions: list[FieldRequirementDecision] = []
    required_fields: list[str] = []
    missing_fields: list[str] = []
    satisfied_fields: list[str] = []
    waived_fields: list[str] = []

    def add_decision(decision: FieldRequirementDecision) -> None:
        decisions.append(decision)
        if decision.required:
            required_fields.append(decision.field)
        if decision.required and not decision.satisfied:
            missing_fields.append(decision.field)
        if decision.satisfied:
            satisfied_fields.append(decision.field)
        if not decision.required and not decision.satisfied:
            waived_fields.append(decision.field)

    business_refs = _evidence_refs(intake, "business_candidate")
    business_confidence = float(intake.confidence_by_field.get("business_candidate") or 0.0)
    has_business = bool(context.business_type)
    business_ambiguities = _ambiguities_for_field(blocking_ambiguities, "business_type")
    business_clarification = "business_type" not in confirmed_field_set and (
        domain_routing.clarification_required or bool(business_ambiguities)
    )
    add_decision(
        FieldRequirementDecision(
            field="business_type",
            required=True,
            satisfied=has_business and not business_clarification,
            satisfaction_source="context.business_type" if has_business else None,
            reason_code="context_business_type" if has_business else "missing_business_type",
            evidence_refs=business_refs,
            confidence=business_confidence or None,
            clarification_required=business_clarification,
            resolution_kind="satisfied" if has_business and not business_clarification else "missing",
        )
    )

    item_decision = _item_or_service_decision(
        context=context,
        intake=intake,
        campaign=campaign,
        routeable=routeable,
        has_blocking_conflicts=bool(blocking_conflicts),
        has_blocking_ambiguities=bool(_ambiguities_for_field(blocking_ambiguities, "item_or_service")),
        confirmed_fields=confirmed_field_set,
        policy=policy,
    )
    add_decision(item_decision)

    promotion_goal_ambiguities = _ambiguities_for_field(blocking_ambiguities, "promotion_goal")
    promotion_goal_refs = (
        _evidence_refs(intake, "campaign_intent_candidate")
        if campaign.campaign_intent and not context.promotion_goal
        else ()
    )
    has_campaign_intent = _campaign_intent_is_usable(campaign, intake, policy)
    has_promotion_goal = bool(context.promotion_goal) or has_campaign_intent
    add_decision(
        FieldRequirementDecision(
            field="promotion_goal",
            required=True,
            satisfied=has_promotion_goal and not bool(promotion_goal_ambiguities),
            satisfaction_source=(
                "context.promotion_goal"
                if context.promotion_goal
                else "campaign_context.campaign_intent"
                if campaign.campaign_intent
                else None
            ),
            reason_code=(
                "context_promotion_goal"
                if context.promotion_goal
                else "campaign_intent_candidate"
                if campaign.campaign_intent
                else "missing_promotion_goal"
            ),
            evidence_refs=promotion_goal_refs,
            confidence=float(intake.confidence_by_field.get("campaign_intent_candidate") or 0.0) or None,
            clarification_required=bool(promotion_goal_ambiguities),
            resolution_kind="satisfied" if has_promotion_goal and not promotion_goal_ambiguities else "missing",
        )
    )

    ad_format_refs = _evidence_refs(intake, "ad_format_candidate")
    has_ad_format = bool(ad_format)
    add_decision(
        FieldRequirementDecision(
            field="ad_format",
            required=True,
            satisfied=has_ad_format,
            satisfaction_source="requested_ad_format" if ad_format else None,
            reason_code="resolved_ad_format" if ad_format else "missing_ad_format",
            evidence_refs=ad_format_refs,
            confidence=float(intake.confidence_by_field.get("ad_format_candidate") or 0.0) or None,
            clarification_required=False,
            resolution_kind="satisfied" if has_ad_format else "missing",
        )
    )

    return IntakeQuestionPolicyDecision(
        required_fields=required_fields,
        missing_fields=missing_fields,
        satisfied_fields=satisfied_fields,
        waived_fields=waived_fields,
        field_decisions=tuple(decisions),
        advertised_subject_used=item_decision.reason_code in {"advertised_subject_item", "waived_by_business_subject_campaign"},
        campaign_intent_used=bool(campaign.campaign_intent and not context.promotion_goal),
        domain_routeable=routeable,
        blocking_ambiguities=blocking_ambiguities,
        blocking_conflicts=blocking_conflict_fields,
        policy_version=POLICY_VERSION,
    )


def _item_or_service_decision(
    *,
    context: MarketingContext,
    intake: IntakeUnderstandingResult,
    campaign: CampaignContext,
    routeable: bool,
    has_blocking_conflicts: bool,
    has_blocking_ambiguities: bool,
    confirmed_fields: set[str],
    policy: IntakeQuestionPolicyConfig,
) -> FieldRequirementDecision:
    if context.item_or_service:
        return FieldRequirementDecision(
            field="item_or_service",
            required=True,
            satisfied=True,
            satisfaction_source="context.item_or_service",
            reason_code="context_item_or_service",
            evidence_refs=_evidence_refs(intake, "product_or_service_candidate"),
            confidence=float(intake.confidence_by_field.get("product_or_service_candidate") or 0.0) or None,
            clarification_required=False,
            resolution_kind="satisfied",
        )

    subject_type = (intake.advertised_subject_type or "").strip().lower()
    subject_confidence = float(intake.confidence_by_field.get("advertised_subject") or 0.0)
    subject_refs = _evidence_refs(intake, "advertised_subject")
    intent = (campaign.campaign_intent or "").strip().lower()
    subject_requirement = campaign_intent_subject_requirement(intent)

    if (
        subject_type in PRODUCT_OR_SERVICE_TYPES
        and intake.advertised_subject
        and subject_refs
        and subject_confidence >= policy.structured_inference_min_confidence
        and not has_blocking_conflicts
    ):
        return FieldRequirementDecision(
            field="item_or_service",
            required=False,
            satisfied=True,
            satisfaction_source="intake.advertised_subject",
            reason_code="advertised_subject_item",
            evidence_refs=subject_refs,
            confidence=subject_confidence,
            clarification_required=False,
            resolution_kind="satisfied",
        )

    if (
        subject_type in BUSINESS_SUBJECT_TYPES
        and intake.advertised_subject
        and subject_refs
        and subject_confidence >= policy.structured_inference_min_confidence
        and is_business_level_campaign_intent(intent)
        and routeable
        and not has_blocking_conflicts
        and not has_blocking_ambiguities
    ):
        return FieldRequirementDecision(
            field="item_or_service",
            required=False,
            satisfied=False,
            satisfaction_source="intake.advertised_subject",
            reason_code="waived_by_business_subject_campaign",
            evidence_refs=subject_refs,
            confidence=subject_confidence,
            clarification_required=False,
            resolution_kind="waived",
        )

    if (
        is_item_level_campaign_intent(intent)
        or subject_requirement in {"product", "menu_or_product", "service"}
        or subject_type in BUSINESS_SUBJECT_TYPES
    ):
        return FieldRequirementDecision(
            field="item_or_service",
            required=True,
            satisfied=False,
            satisfaction_source=None,
            reason_code="missing_item_or_service",
            evidence_refs=subject_refs,
            confidence=subject_confidence or None,
            clarification_required=has_blocking_conflicts or has_blocking_ambiguities,
            resolution_kind="missing",
        )

    return FieldRequirementDecision(
        field="item_or_service",
        required=True,
        satisfied=False,
        satisfaction_source=None,
        reason_code="missing_item_or_service",
        evidence_refs=subject_refs,
        confidence=subject_confidence or None,
        clarification_required=has_blocking_conflicts or has_blocking_ambiguities,
        resolution_kind="missing",
    )


def _evidence_refs(intake: IntakeUnderstandingResult, key: str) -> tuple[str, ...]:
    refs = [
        item.evidence_id
        for item in intake.evidence_items
        if item.key == key and item.evidence_id
    ]
    return tuple(dict.fromkeys(refs))


def _ambiguities_for_field(ambiguity_flags: Sequence[str], field: str) -> tuple[str, ...]:
    return tuple(
        flag
        for flag in ambiguity_flags
        if field in AMBIGUITY_FIELD_MAP.get(flag, set())
    )


def _campaign_intent_is_usable(
    campaign: CampaignContext,
    intake: IntakeUnderstandingResult,
    policy: IntakeQuestionPolicyConfig,
) -> bool:
    if not campaign.campaign_intent:
        return False
    refs = _evidence_refs(intake, "campaign_intent_candidate")
    confidence = float(intake.confidence_by_field.get("campaign_intent_candidate") or 0.0)
    return bool(refs) and confidence >= policy.structured_inference_min_confidence
