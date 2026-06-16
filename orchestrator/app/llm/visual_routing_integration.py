"""A-8 shadow-only visual routing integration for image prompt planning."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchestrator.app.llm.business_context_service import build_business_environment_context_from_domain_routing
from orchestrator.app.llm.creative_routing_context_service import build_creative_routing_context
from orchestrator.app.llm.domain_routing import DomainRoutingResult
from orchestrator.app.llm.product_visual_context_service import product_visual_context_from_understanding
from orchestrator.app.schemas.campaign_context import CampaignContext
from orchestrator.app.schemas.creative_routing import CreativeRoutingContext
from orchestrator.app.schemas.llm_marketing import AdFormatSpec, MarketingContext
from orchestrator.app.schemas.product_understanding import ProductUnderstanding
from orchestrator.app.schemas.product_visual_context import ProductVisualContext
from orchestrator.app.schemas.visual_semantic_intent import VisualSemanticIntent
from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource
from orchestrator.app.schemas.visual_strategy_resolution import VisualStrategyRuntimeContext


VISUAL_ROUTING_METADATA_VERSION = "image-prompt-visual-routing-shadow-v1"
_TRACE_ERROR_STAGE_UNKNOWN = "unknown"
_ALLOWED_TRACE_ERROR_STAGES = frozenset({"trace_build"})
_UNKNOWN_EXCEPTION_TYPE = "UnexpectedError"
_ALLOWED_EXCEPTION_TYPES = frozenset(
    {
        "RuntimeError",
        "ValueError",
        "KeyError",
        "TypeError",
        "AttributeError",
        "ValidationError",
    }
)

_DEFAULT_AD_FORMAT = "instagram_feed"
_DEFAULT_PLATFORM = "instagram"
_DEFAULT_ASPECT_RATIO = "1:1"
_DEFAULT_SIZE = 1024
_DEFAULT_OUTPUT_STRATEGY = "generate_text_free_background_then_overlay"
_FALLBACK_PRODUCT_EVIDENCE_REF = "state:context.item_or_service"
_DEFAULT_PRODUCT_CATEGORY = "other"
_DEFAULT_PRODUCT_CONFIDENCE = 0.5

_ALLOWED_PRODUCT_CATEGORIES = frozenset(
    {
        "food_and_beverage",
        "beauty_and_personal_care",
        "fashion_and_lifestyle",
        "home_and_living",
        "technology",
        "local_service",
        "hospitality",
        "health_and_wellness",
        "education",
        "entertainment_and_media",
        "automotive",
        "other",
    }
)
_ALLOWED_AD_FORMATS = frozenset(
    {
        "instagram_feed",
        "instagram_story",
        "poster",
        "flyer",
        "product_detail",
        "banner",
    }
)
_ALLOWED_PLATFORMS = frozenset(
    {
        "instagram",
        "offline",
        "web",
        "naver_smartstore",
        "naver_place",
        "danggeun",
        "etc",
    }
)
_ALLOWED_ASPECT_RATIOS = frozenset({"1:1", "4:5", "9:16", "16:9", "A4_vertical", "custom"})
_ALLOWED_INFORMATION_DENSITIES = frozenset({"low", "medium", "high"})
_ALLOWED_VISUAL_PRIORITIES = frozenset(
    {
        "product_hero",
        "mood_first",
        "information_first",
        "detail_explanation",
        "click_conversion",
    }
)
_ALLOWED_OUTPUT_STRATEGIES = frozenset(
    {
        "generate_text_free_background_then_overlay",
        "template_composite",
        "multi_section_layout",
        "product_preserving_edit",
        "typography_only",
    }
)


def resolve_visual_routing_mode(state: Mapping[str, Any] | None) -> RoutingMode:
    """Resolve the A-8 routing mode.

    The first A-8 PR is shadow-only. A requested canonical mode is coerced to
    SHADOW so production output cannot switch to canonical route selection.
    """

    state = state or {}
    render_options = state.get("render_options") if isinstance(state, Mapping) else {}
    raw_mode = None
    if isinstance(render_options, Mapping):
        raw_mode = render_options.get("visual_routing_mode")
    raw_mode = raw_mode or state.get("visual_routing_mode")
    normalized = str(raw_mode or RoutingMode.SHADOW.value).strip().lower()
    if normalized == RoutingMode.LEGACY.value:
        return RoutingMode.LEGACY
    return RoutingMode.SHADOW


def build_fail_open_visual_routing_metadata(
    *,
    mode: RoutingMode,
    exception: Exception,
    stage: str,
) -> dict[str, Any]:
    return {
        "routing_mode": mode.value,
        "active_source": RoutingSource.LEGACY.value,
        "trace_available": False,
        "trace_error": {
            "stage": _sanitize_trace_error_stage(stage),
            "exception_type": _sanitize_exception_type(exception),
        },
    }


def build_visual_strategy_runtime_context(
    *,
    state: Mapping[str, Any],
    ad_format_spec: Mapping[str, Any],
) -> VisualStrategyRuntimeContext:
    ad_format = _read_ad_format_spec(ad_format_spec, state=state)
    return VisualStrategyRuntimeContext(
        placement=ad_format.ad_format,
        campaign_roles=frozenset(),
    )


def build_visual_strategy_context_for_shadow(
    *,
    state: Mapping[str, Any],
    marketing_context: MarketingContext,
    domain_result: DomainRoutingResult,
) -> CreativeRoutingContext:
    """Build a CreativeRoutingContext for the visual strategy resolver shadow run."""

    product = _read_or_build_product_understanding(state, marketing_context=marketing_context)
    product_visual = _read_or_build_product_visual_context(state, product=product)
    business = build_business_environment_context_from_domain_routing(domain_result)
    promotion_goal = _string_or_none(marketing_context.promotion_goal) or _string_or_none(
        state.get("promotion_goal")
    )
    campaign = CampaignContext(
        promotion_goal=promotion_goal,
        evidence_refs=("state:context.promotion_goal",) if promotion_goal else (),
        confidence=0.8 if promotion_goal else 0.0,
    )
    ad_format = _read_ad_format_spec(state.get("ad_format_spec"), state=state)

    return build_creative_routing_context(
        domain=domain_result,
        business=business,
        product=product,
        product_visual=product_visual,
        campaign=campaign,
        ad_format=ad_format,
        reference_style_profile=_read_reference_style_profile(state),
        resolver_version=VISUAL_ROUTING_METADATA_VERSION,
    )


def build_visual_semantic_intent_for_shadow(
    state: Mapping[str, Any],
    routing_context: CreativeRoutingContext,
) -> VisualSemanticIntent:
    product_visual = routing_context.product_visual
    return VisualSemanticIntent(
        subject_priority=0.7,
        environment_priority=0.3,
        text_priority=0.5,
        desired_moods=_dedupe_strings([_selected_tone(state)]),
        required_visual_facts=_dedupe_strings(
            [
                *product_visual.product_tags,
                *product_visual.visible_attributes,
                *product_visual.explicit_preparation_methods,
            ]
        ),
        prohibited_visual_elements=_dedupe_strings(product_visual.prohibited_visual_inferences),
        copy_presence_mode="overlay_text_allowed",
        confidence=product_visual.confidence,
    )


def _sanitize_trace_error_stage(stage: str) -> str:
    if stage in _ALLOWED_TRACE_ERROR_STAGES:
        return stage
    return _TRACE_ERROR_STAGE_UNKNOWN


def _sanitize_exception_type(exception: Exception) -> str:
    exception_type = exception.__class__.__name__
    if exception_type in _ALLOWED_EXCEPTION_TYPES:
        return exception_type
    return _UNKNOWN_EXCEPTION_TYPE


def _read_or_build_product_understanding(
    state: Mapping[str, Any],
    *,
    marketing_context: MarketingContext,
) -> ProductUnderstanding:
    raw = state.get("product_understanding")
    if isinstance(raw, ProductUnderstanding):
        return raw
    if isinstance(raw, Mapping):
        return _normalize_product_understanding_input(raw, marketing_context=marketing_context)

    product_name = _string_or_none(marketing_context.item_or_service) or "advertising subject"
    return ProductUnderstanding(
        product_name=product_name,
        broad_category=_DEFAULT_PRODUCT_CATEGORY,
        category_path=[_DEFAULT_PRODUCT_CATEGORY],
        product_name_evidence_ids=[_FALLBACK_PRODUCT_EVIDENCE_REF],
        confidence=_DEFAULT_PRODUCT_CONFIDENCE,
    )


def _normalize_product_understanding_input(
    raw: Mapping[str, Any],
    *,
    marketing_context: MarketingContext,
) -> ProductUnderstanding:
    data = dict(raw)
    product_name = _string_or_none(data.get("product_name")) or _string_or_none(marketing_context.item_or_service)
    data["product_name"] = product_name or "advertising subject"

    category_path = _dedupe_strings(data.get("category_path"))
    broad_category = _allowed_string(data.get("broad_category"), _ALLOWED_PRODUCT_CATEGORIES)
    if not broad_category:
        broad_category = category_path[0] if category_path and category_path[0] in _ALLOWED_PRODUCT_CATEGORIES else None
    if not broad_category:
        broad_category = _DEFAULT_PRODUCT_CATEGORY
    if not category_path or category_path[0] != broad_category:
        category_path = (broad_category,)
    data["broad_category"] = broad_category
    data["category_path"] = list(category_path)

    if not _dedupe_strings(data.get("product_name_evidence_ids")):
        data["product_name_evidence_ids"] = [_FALLBACK_PRODUCT_EVIDENCE_REF]
    if data.get("confidence") is None:
        data["confidence"] = _DEFAULT_PRODUCT_CONFIDENCE
    return ProductUnderstanding(**data)


def _read_or_build_product_visual_context(
    state: Mapping[str, Any],
    *,
    product: ProductUnderstanding,
) -> ProductVisualContext:
    raw = state.get("product_visual_context")
    if isinstance(raw, ProductVisualContext):
        return _normalize_product_visual_context_input(raw, product=product)
    if isinstance(raw, Mapping):
        return _normalize_product_visual_context_input(raw, product=product)

    return product_visual_context_from_understanding(
        product,
        supplement_evidence_refs=_product_evidence_refs(product),
    )


def _normalize_product_visual_context_input(
    raw: ProductVisualContext | Mapping[str, Any],
    *,
    product: ProductUnderstanding,
) -> ProductVisualContext:
    data = raw.model_dump() if isinstance(raw, ProductVisualContext) else dict(raw)
    if _string_or_none(data.get("product_name")) is None:
        data["product_name"] = product.product_name
    if not _dedupe_strings(data.get("category_path")):
        data["category_path"] = product.category_path
    if not _dedupe_strings(data.get("evidence_refs")):
        data["evidence_refs"] = _product_evidence_refs(product)
    if data.get("confidence") is None:
        data["confidence"] = product.confidence
    return ProductVisualContext(**data)


def _read_ad_format_spec(
    raw: AdFormatSpec | Mapping[str, Any] | None,
    *,
    state: Mapping[str, Any] | None = None,
) -> AdFormatSpec:
    if isinstance(raw, AdFormatSpec):
        return raw
    source = dict(raw) if isinstance(raw, Mapping) else {}
    state = state or {}
    ad_format = _allowed_string(source.get("ad_format"), _ALLOWED_AD_FORMATS)
    ad_format = ad_format or _allowed_string(state.get("selected_ad_format"), _ALLOWED_AD_FORMATS)
    ad_format = ad_format or _allowed_string(state.get("requested_ad_format"), _ALLOWED_AD_FORMATS)
    ad_format = ad_format or _DEFAULT_AD_FORMAT
    data = {
        "ad_format": ad_format,
        "platform": (
            _allowed_string(source.get("platform"), _ALLOWED_PLATFORMS)
            or _allowed_string(state.get("requested_platform"), _ALLOWED_PLATFORMS)
            or _DEFAULT_PLATFORM
        ),
        "aspect_ratio": _allowed_string(source.get("aspect_ratio"), _ALLOWED_ASPECT_RATIOS) or _DEFAULT_ASPECT_RATIO,
        "width": _positive_int_or_default(source.get("width"), _DEFAULT_SIZE),
        "height": _positive_int_or_default(source.get("height"), _DEFAULT_SIZE),
        "output_strategy": (
            _allowed_string(source.get("output_strategy"), _ALLOWED_OUTPUT_STRATEGIES)
            or _DEFAULT_OUTPUT_STRATEGY
        ),
        "information_density": _allowed_string(source.get("information_density"), _ALLOWED_INFORMATION_DENSITIES)
        or "medium",
        "visual_priority": _allowed_string(source.get("visual_priority"), _ALLOWED_VISUAL_PRIORITIES)
        or "mood_first",
        "metadata": _metadata_or_empty(source.get("metadata")),
    }
    return AdFormatSpec(**data)


def _string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _allowed_string(value: Any, allowed: frozenset[str]) -> str | None:
    item = _string_or_none(value)
    if item is None or item not in allowed:
        return None
    return item


def _positive_int_or_default(value: Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return default
    return value


def _metadata_or_empty(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _dedupe_strings(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    candidates = [values] if isinstance(values, str) else values
    output: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        item = _string_or_none(value)
        if item is None or item in seen:
            continue
        output.append(item)
        seen.add(item)
    return tuple(output)


def _product_evidence_refs(product: ProductUnderstanding) -> tuple[str, ...]:
    refs = [
        *product.product_name_evidence_ids,
        *[item.evidence_id for item in product.verified_facts],
        *[item.evidence_id for item in product.visual_observations],
        *[item.evidence_id for item in product.permissible_inferences],
    ]
    return _dedupe_strings(refs) or (_FALLBACK_PRODUCT_EVIDENCE_REF,)


def _read_reference_style_profile(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    raw = state.get("reference_style_profile")
    if isinstance(raw, Mapping):
        return dict(raw)
    raw = state.get("text_style_spec")
    if isinstance(raw, Mapping):
        profile = _string_or_none(raw.get("profile"))
        return {"profile": profile} if profile else None
    return None


def _selected_tone(state: Mapping[str, Any]) -> str | None:
    tone = _string_or_none(state.get("selected_tone")) or _string_or_none(state.get("tone"))
    if tone:
        return tone
    style_spec = state.get("text_style_spec")
    if isinstance(style_spec, Mapping):
        return _string_or_none(style_spec.get("profile"))
    return None
