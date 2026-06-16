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
    explicit_refs = normalize_string_list(evidence_refs)
    upstream_refs_by_key: dict[str, list[str]] = {}
    for item in input_evidence.explicit_user_facts:
        if item.key not in CAMPAIGN_EVIDENCE_KEYS:
            continue
        upstream_refs_by_key.setdefault(item.key, []).append(item.evidence_id)

    campaign_field_values = {
        "campaign_intent": input_evidence.campaign_intent,
        "campaign_status": input_evidence.campaign_status,
        "promotion_goal": input_evidence.promotion_goal,
        "desired_positioning": input_evidence.desired_positioning,
    }
    missing_evidence_fields = [
        key
        for key, value in campaign_field_values.items()
        if value and not upstream_refs_by_key.get(key)
    ]
    if missing_evidence_fields and not explicit_refs:
        raise ValueError("campaign fields require matching evidence: " + ", ".join(missing_evidence_fields))

    upstream_refs = [ref for refs in upstream_refs_by_key.values() for ref in refs]
    merged_refs = normalize_string_list([*upstream_refs, *explicit_refs])
    resolved_confidence = input_evidence.overall_confidence if confidence is None else confidence
    return build_campaign_context(
        campaign_intent=input_evidence.campaign_intent,
        campaign_status=input_evidence.campaign_status,
        promotion_goal=input_evidence.promotion_goal,
        desired_positioning=input_evidence.desired_positioning,
        evidence_refs=merged_refs,
        confidence=resolved_confidence,
    )
