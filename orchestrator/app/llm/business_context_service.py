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
