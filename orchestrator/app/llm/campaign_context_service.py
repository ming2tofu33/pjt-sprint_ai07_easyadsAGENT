"""Deterministic assembly for campaign input context."""

from __future__ import annotations

from collections.abc import Iterable

from orchestrator.app.schemas.campaign_context import CampaignContext, normalize_string_list
from orchestrator.app.schemas.input_evidence import InputEvidenceBundle


CAMPAIGN_EVIDENCE_KEYS = frozenset(
    {
        "campaign_intent",
        "campaign_status",
        "promotion_goal",
        "desired_positioning",
    }
)


def build_campaign_context(
    *,
    campaign_intent: str | None = None,
    campaign_status: str | None = None,
    promotion_goal: str | None = None,
    desired_positioning: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
    confidence: float,
) -> CampaignContext:
    return CampaignContext(
        campaign_intent=campaign_intent,
        campaign_status=campaign_status,
        promotion_goal=promotion_goal,
        desired_positioning=desired_positioning,
        evidence_refs=evidence_refs,
        confidence=confidence,
    )


def campaign_context_from_input_evidence(
    input_evidence: InputEvidenceBundle,
    *,
    evidence_refs: Iterable[str] = (),
    confidence: float | None = None,
) -> CampaignContext:
    upstream_refs = [
        item.evidence_id
        for item in input_evidence.explicit_user_facts
        if item.key in CAMPAIGN_EVIDENCE_KEYS
    ]
    merged_refs = normalize_string_list([*upstream_refs, *evidence_refs])
    resolved_confidence = input_evidence.overall_confidence if confidence is None else confidence
    return build_campaign_context(
        campaign_intent=input_evidence.campaign_intent,
        campaign_status=input_evidence.campaign_status,
        promotion_goal=input_evidence.promotion_goal,
        desired_positioning=input_evidence.desired_positioning,
        evidence_refs=merged_refs,
        confidence=resolved_confidence,
    )
