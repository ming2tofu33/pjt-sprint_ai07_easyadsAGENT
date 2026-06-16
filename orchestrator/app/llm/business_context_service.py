"""Deterministic assembly for business environment context."""

from __future__ import annotations

from collections.abc import Iterable

from orchestrator.app.llm.domain_routing import DomainRoutingResult
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext


def build_business_environment_context(
    domain_result: DomainRoutingResult,
    *,
    venue_type: str | None = None,
    service_model: str | None = None,
    business_tags: Iterable[str] = (),
    environment_tags: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
    confidence: float | None = None,
) -> BusinessEnvironmentContext:
    return BusinessEnvironmentContext(
        broad_domain=domain_result.canonical_domain,
        venue_type=venue_type,
        service_model=service_model,
        business_tags=business_tags,
        environment_tags=environment_tags,
        evidence_refs=evidence_refs,
        confidence=domain_result.confidence if confidence is None else confidence,
    )


def build_business_environment_context_from_domain_routing(
    domain_result: DomainRoutingResult,
    *,
    venue_type: str | None = None,
    service_model: str | None = None,
    additional_business_tags: Iterable[str] = (),
    additional_environment_tags: Iterable[str] = (),
    additional_evidence_refs: Iterable[str] = (),
    confidence: float | None = None,
) -> BusinessEnvironmentContext:
    routing_tags = tuple(tag.tag for tag in domain_result.business_tags if tag.usable_for_routing)
    routing_evidence = tuple(tag.evidence_ref for tag in domain_result.business_tags if tag.usable_for_routing and tag.evidence_ref)
    return BusinessEnvironmentContext(
        broad_domain=domain_result.canonical_domain,
        venue_type=venue_type,
        service_model=service_model,
        business_tags=(*routing_tags, *additional_business_tags),
        environment_tags=additional_environment_tags,
        evidence_refs=(*domain_result.evidence_refs, *routing_evidence, *additional_evidence_refs),
        confidence=domain_result.confidence if confidence is None else confidence,
    )
