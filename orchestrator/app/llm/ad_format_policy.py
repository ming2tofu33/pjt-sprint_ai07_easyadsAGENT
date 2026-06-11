"""Deterministic ad format and copy presence policy."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.app.schemas.ad_format import (
    AdFormatContract,
    CopyPresencePlan,
    CreativeLaneDecision,
    InformationPanelPlan,
    PlatformSafeZoneSpec,
)


FORMAT_ALIASES = {
    "instagram_feed": "instagram_feed_static",
    "instagram-feed": "instagram_feed_static",
    "feed": "instagram_feed_static",
    "instagram_story": "instagram_story",
    "story": "instagram_story",
    "poster": "print_poster",
    "print_poster": "print_poster",
    "flyer": "offline_flyer",
    "landing": "landing_page_hero",
    "landing_page": "landing_page_hero",
    "product_detail": "product_detail_hero",
    "square": "generic_social_square",
    "generic_social_square": "generic_social_square",
    "menu_board": "menu_board",
    "store_signage": "store_signage",
}


def build_ad_format_contract(state: dict[str, Any]) -> AdFormatContract:
    placement = _resolve_placement(state)
    required = _required_information_fields(state)
    lane = "information_design" if _requires_information_design(state, required) else "visual_first"
    if placement == "instagram_story":
        return AdFormatContract(
            placement="instagram_story",
            aspect_ratio="9:16",
            interaction_mode="platform_interactive",
            platform_cta_available=True,
            embedded_cta_policy="platform_only",
            platform_safe_zones=PlatformSafeZoneSpec(top_ratio=0.10, bottom_ratio=0.12, reserved_for_platform_ui=["story_header", "platform_cta"]),
            creative_lane=lane,
            text_density_range="medium" if lane == "information_design" else "low",
            required_information_fields=required,
            rationale=["instagram_story_uses_platform_cta", "bottom_safe_zone_reserved"],
        )
    if placement == "landing_page_hero":
        return AdFormatContract(
            placement="landing_page_hero",
            aspect_ratio="16:9",
            interaction_mode="html_or_landing_page",
            platform_cta_available=True,
            embedded_cta_policy="forbidden",
            platform_safe_zones=PlatformSafeZoneSpec(),
            creative_lane=lane,
            text_density_range="medium" if lane == "information_design" else "minimal",
            caption_channel_available=False,
            required_information_fields=required,
            rationale=["html_cta_lives_outside_image"],
        )
    if placement in {"print_poster", "offline_flyer", "menu_board", "store_signage"}:
        return AdFormatContract(
            placement=placement,  # type: ignore[arg-type]
            aspect_ratio="1:1" if placement == "print_poster" else "3:4",
            interaction_mode="print_or_offline",
            platform_cta_available=False,
            embedded_cta_policy="optional",
            platform_safe_zones=PlatformSafeZoneSpec(),
            creative_lane="information_design" if required else lane,
            text_density_range="high" if required else "medium",
            required_information_fields=required,
            rationale=["offline_action_information_requires_verified_destination" if required else "offline_without_destination_disallows_fake_button"],
        )
    return AdFormatContract(
        placement=placement,  # type: ignore[arg-type]
        aspect_ratio="1:1",
        interaction_mode="non_interactive_image",
        platform_cta_available=False,
        embedded_cta_policy="forbidden",
        platform_safe_zones=PlatformSafeZoneSpec(),
        creative_lane=lane,
        text_density_range="medium" if lane == "information_design" else "minimal",
        caption_channel_available=True,
        required_information_fields=required,
        rationale=["static_social_image_uses_caption_channel", "embedded_button_cta_forbidden"],
    )


def decide_creative_lane(state: dict[str, Any], contract: AdFormatContract | None = None) -> CreativeLaneDecision:
    contract = contract or build_ad_format_contract(state)
    required = list(contract.required_information_fields)
    reasons: list[str] = []
    if len(required) >= 3:
        reasons.append("product_explanation_required")
    if _has_discount(state):
        reasons.append("discount_present")
    if _has_price(state):
        reasons.append("price_present")
    if _has_period(state):
        reasons.append("period_present")
    if _benefit_count(state) >= 2:
        reasons.append("multiple_verified_benefits")
    if _goal(state) in {"discount_event", "conversion", "reservation_cta", "lower_funnel_conversion"}:
        reasons.append("lower_funnel_conversion")
    if not reasons:
        reasons.extend(["image_has_high_explanatory_power", "editorial_visual_priority"])
    lane = "information_design" if contract.creative_lane == "information_design" or any(reason in reasons for reason in {"discount_present", "price_present", "period_present", "multiple_verified_benefits", "product_explanation_required", "lower_funnel_conversion"}) else "visual_first"
    archetype = _archetype_for(state, lane, reasons, contract)
    return CreativeLaneDecision(lane=lane, archetype=archetype, reason_codes=_dedupe(reasons), confidence=0.86 if lane == contract.creative_lane else 0.74)


def build_copy_presence_plan(contract: AdFormatContract, lane: CreativeLaneDecision, state: dict[str, Any] | None = None) -> CopyPresencePlan:
    forbidden = []
    if contract.embedded_cta_policy in {"forbidden", "platform_only"}:
        forbidden.extend(["cta", "embedded_action_cta"])
    if lane.lane == "visual_first":
        if lane.archetype == "visual_minimal":
            mode = "brand_only"
            allowed = ["brand_label", "headline"]
            max_area = 0.06
            blocks = 1
        else:
            mode = "headline_only"
            allowed = ["headline"]
            max_area = 0.10
            blocks = 1
        return CopyPresencePlan(mode=mode, allowed_roles=allowed, forbidden_roles=_dedupe(forbidden + ["price", "promotion", "badge", "body"]), max_text_area_ratio=min(max_area, 0.15), min_text_area_ratio=0.0, visual_intrusion_budget=0.18, no_text_allowed=True, max_message_blocks=blocks, rationale=["visual_first_preserves_image", "text_area_cap_15_percent"])
    if lane.archetype == "promotion_sale_poster":
        mode = "full_information_poster"
        allowed = ["headline", "subheadline", "promotion", "discount", "period", "price", "body", "badge", "store_info"]
        min_area, max_area, blocks = 0.40, 0.65, 8
    elif lane.archetype == "product_information_poster":
        mode = "product_benefit_summary"
        allowed = ["headline", "subheadline", "body", "badge", "store_info"]
        min_area, max_area, blocks = 0.30, 0.50, 6
    else:
        mode = "product_benefit_summary"
        allowed = ["headline", "subheadline", "body", "promotion", "badge"]
        min_area, max_area, blocks = 0.20, 0.35, 5
    return CopyPresencePlan(mode=mode, allowed_roles=[role for role in allowed if role not in forbidden], forbidden_roles=_dedupe(forbidden), max_text_area_ratio=max_area, min_text_area_ratio=min_area, visual_intrusion_budget=0.65, no_text_allowed=False, max_message_blocks=blocks, rationale=["information_design_requires_structured_copy", "budget_scored_by_completeness_and_scanability"])


def build_information_panel_plan(contract: AdFormatContract, lane: CreativeLaneDecision) -> InformationPanelPlan:
    if lane.lane == "visual_first":
        return InformationPanelPlan(enabled=False, panel_type="none", geometry="none", coverage_ratio=0.0, background_treatment="none", product_zone="background_full", hierarchy_zones=[])
    if lane.archetype == "promotion_sale_poster":
        return InformationPanelPlan(enabled=True, panel_type="split_screen_diagonal_panel", geometry="diagonal", coverage_ratio=0.55, background_treatment="soft_solid", product_zone="right", hierarchy_zones=["headline_zone", "promotion_badge_zone", "price_zone", "period_zone", "footer_benefit_strip"])
    if lane.archetype == "product_information_poster":
        return InformationPanelPlan(enabled=True, panel_type="full_poster_grid", geometry="grid", coverage_ratio=0.42, background_treatment="soft_solid", product_zone="right", hierarchy_zones=["headline_zone", "subheadline_zone", "benefit_list_zone", "proof_badge_zone", "footer_benefit_strip"])
    return InformationPanelPlan(enabled=True, panel_type="left_information_column", geometry="rounded_rectangle", coverage_ratio=0.38, background_treatment="soft_gradient", product_zone="right", hierarchy_zones=["headline_zone", "subheadline_zone", "benefit_list_zone", "promotion_badge_zone"], safe_margin_ratio=max(0.05, contract.platform_safe_zones.bottom_ratio))


def role_allowed(role: str, plan: CopyPresencePlan | dict[str, Any] | None) -> bool:
    if not plan:
        return True
    allowed = set(plan.allowed_roles if isinstance(plan, CopyPresencePlan) else plan.get("allowed_roles") or [])
    forbidden = set(plan.forbidden_roles if isinstance(plan, CopyPresencePlan) else plan.get("forbidden_roles") or [])
    if role in forbidden or (role == "cta" and "embedded_action_cta" in forbidden):
        return False
    return not allowed or role in allowed


def _resolve_placement(state: dict[str, Any]) -> str:
    context = state.get("context") or {}
    extra = context.get("extra") if isinstance(context, dict) else {}
    brief = state.get("current_brief") or {}
    raw = (
        state.get("selected_ad_format")
        or brief.get("requested_ad_format")
        or (extra or {}).get("placement")
        or (extra or {}).get("ad_format")
        or "instagram_feed"
    )
    return FORMAT_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())


def _required_information_fields(state: dict[str, Any]) -> list[str]:
    context = state.get("context") or {}
    extra = context.get("extra") if isinstance(context, dict) else {}
    text = " ".join(str(value or "") for value in [state.get("user_input"), context.get("price_or_discount") if isinstance(context, dict) else None, context.get("time_context") if isinstance(context, dict) else None, extra])
    fields = []
    if _has_discount(state):
        fields.append("discount")
    if _has_price(state):
        fields.append("price")
    if _has_period(state):
        fields.append("period")
    if _benefit_count(state) >= 2:
        fields.append("benefits")
    if re.search(r"\b(menu|price list|schedule|event|address|location|qr)\b|메뉴|가격|행사|주소|장소|QR", text, re.I):
        fields.append("action_destination")
    return _dedupe(fields)


def _requires_information_design(state: dict[str, Any], required: list[str]) -> bool:
    required_set = set(required)
    return len(required) >= 3 or {"discount", "period"} <= required_set or {"price", "benefits"} <= required_set or _benefit_count(state) >= 2


def _archetype_for(state: dict[str, Any], lane: str, reasons: list[str], contract: AdFormatContract) -> str:
    if lane == "visual_first":
        return "visual_editorial" if contract.placement in {"instagram_feed_static", "generic_social_square"} else "visual_minimal"
    if contract.placement == "instagram_story" and "multiple_verified_benefits" in reasons:
        return "product_benefit_story"
    if "discount_present" in reasons or "price_present" in reasons:
        return "promotion_sale_poster"
    if "multiple_verified_benefits" in reasons:
        return "product_benefit_story"
    return "product_information_poster"


def _goal(state: dict[str, Any]) -> str:
    context = state.get("context") or {}
    return str(context.get("promotion_goal") or "").lower() if isinstance(context, dict) else ""


def _has_discount(state: dict[str, Any]) -> bool:
    return "%" in _source_text(state) or "discount" in _source_text(state).lower() or "할인" in _source_text(state)


def _has_price(state: dict[str, Any]) -> bool:
    return bool(re.search(r"(\$|₩|원|\d+[,.]?\d*\s?won|\d+[,.]?\d*\s?원)", _source_text(state), re.I))


def _has_period(state: dict[str, Any]) -> bool:
    return bool(re.search(r"(\d{1,2}[./-]\d{1,2}|until|through|기간|까지|부터)", _source_text(state), re.I))


def _benefit_count(state: dict[str, Any]) -> int:
    context = state.get("context") or {}
    extra = context.get("extra") if isinstance(context, dict) else {}
    benefits = (extra or {}).get("benefits") if isinstance(extra, dict) else None
    if isinstance(benefits, list):
        return len([item for item in benefits if item])
    return len(re.findall(r"benefit|효과|장점|탄력|보습|진정|광채|premium|verified", _source_text(state), re.I))


def _source_text(state: dict[str, Any]) -> str:
    context = state.get("context") or {}
    values: list[Any] = [state.get("user_input")]
    if isinstance(context, dict):
        values.extend(
            [
                context.get("business_type"),
                context.get("item_or_service"),
                context.get("promotion_goal"),
                context.get("time_context"),
                context.get("price_or_discount"),
                context.get("location_text"),
                context.get("contact_or_order_method"),
            ]
        )
        extra = context.get("extra")
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key == "ad_format":
                    continue
                values.append(value)
    return " ".join(_flatten_text_value(value) for value in values if value)


def _flatten_text_value(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return " ".join(_flatten_text_value(item) for item in value.values())
    return str(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
