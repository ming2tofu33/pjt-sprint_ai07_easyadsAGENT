"""Deterministic assembly for creative routing context."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from orchestrator.app.llm.domain_routing import DomainRoutingResult
from orchestrator.app.schemas.business_context import BusinessEnvironmentContext
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputConflict
from orchestrator.app.schemas.llm_marketing import AdFormatSpec
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext


def build_creative_routing_context(
    *,
    domain: DomainRoutingResult,
    business: BusinessEnvironmentContext,
    product: ProductUnderstanding,
    product_visual: ProductVisualContext,
    campaign: CampaignContext,
    ad_format: AdFormatSpec,
    visual_observations: Iterable[EvidenceItem] = (),
    reference_style_profile: Mapping[str, Any] | None = None,
    ambiguity_flags: Iterable[str] = (),
    input_conflicts: Iterable[InputConflict] = (),
    resolver_version: str,
) -> CreativeRoutingContext:
    profile = dict(reference_style_profile) if reference_style_profile is not None else None
    return CreativeRoutingContext(
        domain=domain,
        business=business,
        product=product,
        product_visual=product_visual,
        campaign=campaign,
        ad_format=ad_format,
        visual_observations=list(visual_observations),
        reference_style_profile=profile,
        ambiguity_flags=list(ambiguity_flags),
        input_conflicts=list(input_conflicts),
        resolver_version=resolver_version,
    )
