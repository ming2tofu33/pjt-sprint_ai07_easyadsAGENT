"""Campaign-aware planning for native typography single-shot creative."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.input_evidence import InputEvidenceBundle
from orchestrator.app.schemas.native_creative import CampaignMessagePlan, NativeSourceVisualAnalysis, TypographyDominancePlan, VisualSemanticCuePlan
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


LAUNCH_HINTS = ("launch", "new_product", "new_menu", "new menu", "new", "신메뉴", "출시", "새로운", "소개")
EDITORIAL_HINTS = ("brand", "editorial", "mood", "브랜드", "감성", "분위기")
INFO_HINTS = ("information", "detail", "안내", "정보")
OFFER_HINTS = ("offer", "sale", "discount", "할인", "특가")


def plan_native_campaign_message(
    *,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
    placement: str,
    promotion_goal: str,
    source_visual_analysis: NativeSourceVisualAnalysis | None,
    state: dict[str, Any],
) -> CampaignMessagePlan:
    adapter = state.get("native_campaign_message_adapter")
    if adapter:
        payload = adapter.plan_native_campaign_message(
            input_evidence=input_evidence,
            product_understanding=product_understanding,
            placement=placement,
            promotion_goal=promotion_goal,
            source_visual_analysis=source_visual_analysis,
            state=state,
        )
        return CampaignMessagePlan(**payload)

    text = " ".join([promotion_goal or "", placement or "", input_evidence.user_text or "", input_evidence.user_request_utterance or ""]).lower()
    info_ids = {item.evidence_id for item in input_evidence.explicit_user_facts}
    info_ids.update(item.evidence_id for item in (product_understanding.verified_facts or []))
    info_count = len(info_ids)
    has_support_basis = bool(input_evidence.explicit_user_facts or product_understanding.permissible_inferences or input_evidence.creative_inferences)
    image_power = 0.82 if source_visual_analysis and source_visual_analysis.source_suitable else 0.65
    density = "minimal" if info_count <= 1 else ("low" if info_count <= 3 else ("medium" if info_count <= 6 else "high"))

    if any(hint in text for hint in LAUNCH_HINTS):
        return CampaignMessagePlan(
            campaign_role="new_product_introduction",
            primary_communication_goal=promotion_goal or "new_product_launch",
            funnel_stage="awareness",
            image_explanatory_power=image_power,
            verified_information_density=density,
            visible_copy_mode="headline_plus_support" if has_support_basis else "headline_only",
            headline_function="launch_announcement",
            support_function="launch_context" if has_support_basis else "none",
            rationale=["launch_or_introduction_context_detected", "support_allowed_only_when_it_adds_campaign_context"],
            confidence=0.86,
        )
    if any(hint in text for hint in OFFER_HINTS):
        return CampaignMessagePlan(
            campaign_role="offer_announcement",
            primary_communication_goal=promotion_goal or "offer_announcement",
            funnel_stage="conversion",
            image_explanatory_power=image_power,
            verified_information_density=density,
            visible_copy_mode="headline_only",
            headline_function="product_identity",
            support_function="none",
            rationale=["offer_context_requires_verified_offer_details"],
            confidence=0.78,
        )
    if any(hint in text for hint in INFO_HINTS):
        return CampaignMessagePlan(
            campaign_role="information_required",
            primary_communication_goal=promotion_goal or "product_information",
            funnel_stage="consideration",
            image_explanatory_power=image_power,
            verified_information_density=density,
            visible_copy_mode="headline_plus_support" if density in {"medium", "high"} else "headline_only",
            headline_function="product_identity",
            support_function="product_detail" if density in {"medium", "high"} else "none",
            rationale=["information_goal_detected"],
            confidence=0.8,
        )
    if any(hint in text for hint in EDITORIAL_HINTS):
        return CampaignMessagePlan(
            campaign_role="brand_editorial",
            primary_communication_goal=promotion_goal or "brand_editorial",
            funnel_stage="awareness",
            image_explanatory_power=image_power,
            verified_information_density=density,
            visible_copy_mode="headline_only",
            headline_function="brand_statement",
            support_function="brand_mood",
            rationale=["editorial_or_brand_mood_context_detected"],
            confidence=0.78,
        )
    return CampaignMessagePlan(
        campaign_role="menu_identity",
        primary_communication_goal=promotion_goal or input_evidence.campaign_intent or "product_promotion",
        funnel_stage="awareness",
        image_explanatory_power=image_power,
        verified_information_density=density,
        visible_copy_mode="product_name_only" if density == "minimal" else "headline_only",
        headline_function="product_identity",
        support_function="none",
        rationale=["default_product_identity_or_menu_identity", "minimal_verified_information_prefers_minimal_visible_copy"],
        confidence=0.82,
    )


def build_visual_semantic_cue_plan(
    *,
    campaign_plan: CampaignMessagePlan,
    input_evidence: InputEvidenceBundle,
    product_understanding: ProductUnderstanding,
) -> VisualSemanticCuePlan:
    positioning = list(input_evidence.desired_positioning or product_understanding.desired_positioning)
    atmosphere = _visualize_positioning(positioning)
    if campaign_plan.campaign_role == "new_product_introduction":
        atmosphere.extend(["orderly launch presentation", "clear new-menu focus"])
    if campaign_plan.campaign_role == "brand_editorial":
        atmosphere.extend(["editorial restraint", "quiet brand mood"])
    cues = list(dict.fromkeys([*atmosphere, "clean negative space", "product remains primary subject"]))
    return VisualSemanticCuePlan(
        non_display_cues=cues,
        atmosphere_cues=cues,
        material_cues=[],
        sensory_visual_cues=[cue for cue in cues if any(token in cue for token in ["warm", "depth", "texture"])],
        composition_cues=["clear product hierarchy", "controlled negative space"],
        typography_mood_cues=["restrained Hangul typography", "copy does not overpower product"],
        derived_from_positioning=positioning,
        derived_from_visual_evidence=[item.evidence_id for item in input_evidence.visual_observations],
        derived_from_permissible_inference=[item.evidence_id for item in product_understanding.permissible_inferences],
        must_not_render_as_text=cues,
        confidence=0.84,
    )


def plan_typography_dominance(*, campaign_plan: CampaignMessagePlan, placement: str) -> TypographyDominancePlan:
    if campaign_plan.campaign_role == "new_product_introduction":
        return TypographyDominancePlan(
            headline_prominence="balanced",
            headline_scale_intent="medium",
            support_scale_intent="small" if campaign_plan.visible_copy_mode == "headline_plus_support" else "none",
            product_visual_priority=0.74,
            text_visual_priority=0.42,
            preferred_copy_position="adaptive_negative_space" if "instagram" in (placement or "") else "top_left",
            rationale=["new_product_intro_needs_medium_headline_and_smaller_support"],
        )
    if campaign_plan.campaign_role == "brand_editorial":
        return TypographyDominancePlan(
            headline_prominence="quiet",
            headline_scale_intent="small",
            support_scale_intent="caption" if campaign_plan.visible_copy_mode == "headline_plus_support" else "none",
            product_visual_priority=0.78,
            text_visual_priority=0.28,
            preferred_copy_position="adaptive_negative_space",
            rationale=["editorial_role_keeps_copy_subordinate_to_visual_mood"],
        )
    return TypographyDominancePlan(
        headline_prominence="balanced" if campaign_plan.visible_copy_mode == "product_name_only" else "dominant",
        headline_scale_intent="medium" if campaign_plan.visible_copy_mode == "product_name_only" else "large",
        support_scale_intent="none",
        product_visual_priority=0.72,
        text_visual_priority=0.45,
        preferred_copy_position="adaptive_negative_space",
        rationale=["identity_role_allows_clear_product_name_without_support"],
    )


def _visualize_positioning(positioning: list[str]) -> list[str]:
    cues: list[str] = []
    for item in positioning:
        lowered = item.lower()
        if lowered in {"premium", "refined", "고급", "고급진", "정갈한"}:
            cues.extend(["refined and orderly atmosphere", "warm depth with restrained presentation"])
        elif lowered in {"calm", "quiet", "차분한"}:
            cues.append("calm negative space")
        else:
            cues.append(f"{item} visual mood")
    return cues
