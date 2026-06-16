"""Deterministic policy for GPT Image 2 native typography lane."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from orchestrator.app.llm.ad_format_presets import NATIVE_TYPOGRAPHY_SUPPORTED_TEXT_FORMATS, build_ad_format_spec
from orchestrator.app.llm.native_campaign_copy_rules import contains_campaign_modifier, contains_generic_launch_copy
from typing import NamedTuple

from pydantic import ValidationError

from orchestrator.app.schemas.native_creative import (
    ApprovedNativeCopyBrief,
    CreativeExecutionPlan,
    FlyerApprovedCopyPlan,
    FlyerPromotionalApprovedCopyPlan,
    NativeCreativePromptPackage,
    NativeGenerationBudget,
    NativeTypographyEligibilityDecision,
    NativeCopyCandidate,
    NativeCopyScorecard,
    PositioningRealizationPlan,
    ProductDetailApprovedFeaturePlan,
)

GENERIC_CTA_TERMS = {
    "learn more",
    "discover more",
    "find out more",
    "shop now",
    "buy now",
    "order now",
    "지금 확인하기",
    "자세히 보기",
    "메뉴 보기",
    "지금 구매하기",
    "지금 예약하기",
    "지금 만나보세요",
}

BLOCKED_EXACT_TEXT_PATTERNS = [
    r"\d+\s*원",
    r"\d+\s*%",
    r"\d{4}[.-]\d{1,2}[.-]\d{1,2}",
    r"\d{2,4}[-\s]\d{3,4}[-\s]\d{4}",
    r"https?://",
    r"\bqr\b",
]

BLOCKED_CLAIM_WORDS = {
    "무료",
    "할인",
    "최저가",
    "100%",
    "완치",
    "즉시 효과",
    "기적",
    "보장",
    "guaranteed",
    "free",
    "discount",
}

REQUEST_INTENT_PATTERNS = [
    r"홍보(?:하고 싶어|해\s*줘|해주세요)",
    r"광고(?:하고 싶어|해\s*줘|해주세요)",
    r"소개(?:하고 싶어|해\s*줘|해주세요)",
    r"만들어\s*줘",
    r"제작해\s*줘",
    r"디자인해\s*줘",
    r"알리고 싶어",
    r"\bi want to promote\b",
    r"\bcreate an ad\b",
    r"\bmake an advertisement\b",
    r"\badvertise this\b",
    r"\bpromote this\b",
    r"손님\s*많이\s*오게",
    r"많이\s*팔리게",
    r"예약(?:\s*/\s*|\s+및\s+|\s+)?방문\s*유도",
]

DIRECT_POSITIONING_TERMS = {
    "고급",
    "고급진",
    "품격",
    "프리미엄",
    "럭셔리",
    "우아",
    "세련",
    "최고급",
    "명품",
    "특별한",
    "premium",
    "luxury",
    "luxurious",
    "elegant",
    "sophisticated",
    "exclusive",
    "prestigious",
    "high-end",
}
ABSTRACT_PRESTIGE_TERMS = {"품격", "프리미엄", "럭셔리", "우아", "세련", "premium", "luxury", "elegant", "sophisticated"}
SENSORY_LANGUAGE_CUES = {
    "김",
    "따뜻",
    "온기",
    "부드",
    "고소",
    "구수",
    "향",
    "식감",
    "결",
    "fresh",
    "warm",
    "steam",
    "aroma",
    "soft",
    "crisp",
    "texture",
}


def plan_gpt_image2_native_single_shot() -> CreativeExecutionPlan:
    return CreativeExecutionPlan(
        image_engine="gpt_image_2",
        execution_lane="gpt_native_single_shot",
        copy_authoring_mode="gpt_structured",
        text_rendering_mode="native_typography",
        copy_precision="exact",
        max_text_blocks=2,
        native_text_allowed=True,
        reason_codes=["single_image_call", "native_typography_requested", "no_external_renderer"],
    )


def decide_native_typography_eligibility(copy_brief: ApprovedNativeCopyBrief | None = None, *, required_text: bool = True) -> NativeTypographyEligibilityDecision:
    if copy_brief is None:
        return NativeTypographyEligibilityDecision(eligible=True, recommended_lane="gpt_native_single_shot", max_text_blocks=2, max_total_characters=48, confidence=0.75)
    failures = validate_approved_native_copy_brief(copy_brief)
    if failures and required_text:
        return NativeTypographyEligibilityDecision(eligible=False, recommended_lane="manual_review", blocking_reasons=failures, max_text_blocks=copy_brief.max_text_blocks, max_total_characters=copy_brief.max_total_characters, confidence=0.9)
    if failures:
        return NativeTypographyEligibilityDecision(eligible=False, recommended_lane="gpt_image_only_single_shot", blocking_reasons=failures, max_text_blocks=0, max_total_characters=0, confidence=0.8)
    return NativeTypographyEligibilityDecision(eligible=True, recommended_lane="gpt_native_single_shot", reason_codes=["brief_passed_native_policy"], max_text_blocks=copy_brief.max_text_blocks, max_total_characters=copy_brief.max_total_characters, confidence=0.9)


def validate_approved_native_copy_brief(brief: ApprovedNativeCopyBrief) -> list[str]:
    failures: list[str] = []
    texts = [text for text in [brief.headline, brief.supporting_copy, brief.closing_copy, brief.action_cta] if text]
    if brief.compliance_status != "approved":
        failures.append("copy_brief_not_approved")
    if not brief.headline:
        failures.append("headline_missing")
    if len(texts) > 2 or brief.max_text_blocks > 2:
        failures.append("text_block_limit_exceeded")
    if sum(len(text) for text in texts) > min(brief.max_total_characters, 48):
        failures.append("character_budget_exceeded")
    if brief.supporting_copy and brief.closing_copy:
        failures.append("support_and_closing_both_present")
    if brief.action_cta:
        failures.append("action_cta_requires_verified_destination")
    lowered = " ".join(texts).lower()
    if any(term in lowered for term in GENERIC_CTA_TERMS):
        failures.append("generic_cta_detected")
    if any(word.lower() in lowered for word in BLOCKED_CLAIM_WORDS):
        failures.append("blocked_claim_detected")
    if any(re.search(pattern, " ".join(texts), re.IGNORECASE) for pattern in BLOCKED_EXACT_TEXT_PATTERNS):
        failures.append("exact_operational_text_detected")
    if brief.language == "korean" and brief.headline and re.search(r"\b(discover|meet|learn more)\b", brief.headline, re.IGNORECASE):
        failures.append("english_generic_headline_for_korean_context")
    if len({text.strip() for text in texts}) != len(texts):
        failures.append("duplicate_copy_text")
    joined = " ".join([*texts, brief.product_identity or ""])
    if _contains_request_intent(joined):
        failures.append("meta_instruction_leakage_detected")
    if brief.product_identity and _contains_request_intent(brief.product_identity):
        failures.append("product_identity_contaminated")
    source_request = brief.source_user_request or ""
    if brief.copy_source_mode == "generated":
        if not brief.transformation_performed:
            failures.append("copy_transformation_missing")
        if source_request and brief.headline and _contains_request_intent(source_request) and _similarity(source_request, brief.headline) >= 0.90:
            failures.append("user_request_copied_as_headline")
    if not set(brief.product_evidence_ids or brief.verified_evidence_ids) and brief.copy_source_mode != "user_exact":
        failures.append("copy_provenance_missing")
    score = score_native_copy_candidate(
        NativeCopyCandidate(
            candidate_id=brief.selected_candidate_id or "brief",
            strategy="product_name_first",
            headline=brief.headline or "",
            supporting_copy=brief.supporting_copy,
            closing_copy=brief.closing_copy,
            action_cta=brief.action_cta,
            headline_basis_ids=brief.product_evidence_ids or brief.verified_evidence_ids,
            support_basis_ids=brief.copy_claim_evidence_ids or (brief.product_evidence_ids if brief.supporting_copy or brief.closing_copy else []),
            support_basis_type=brief.support_basis_type,
            language=brief.language,
            text_block_count=min(len(texts) or 1, 2),
            total_character_count=sum(len(text) for text in texts),
        ),
        product_identity=brief.product_identity,
        requested_positioning=brief.desired_positioning,
        exact_user_copy=brief.copy_source_mode == "user_exact",
    )
    if score.blocked and brief.copy_source_mode != "user_exact":
        failures.extend(score.blocking_reasons)
    return sorted(set(failures))


def direct_positioning_terms_used(text: str | None) -> list[str]:
    lowered = (text or "").lower()
    return sorted(term for term in DIRECT_POSITIONING_TERMS if term.lower() in lowered)


def build_positioning_realization_plan(*, requested_positioning: list[str], exact_user_copy: bool = False) -> PositioningRealizationPlan:
    direct_terms = sorted(set(requested_positioning) & DIRECT_POSITIONING_TERMS)
    if exact_user_copy:
        return PositioningRealizationPlan(
            requested_positioning=requested_positioning,
            realization_mode="explicit",
            copy_expression_policy="exact_user_copy",
            preferred_channels=["product_copy"],
            copy_should_carry_positioning=True,
            direct_positioning_terms_allowed=direct_terms,
            direct_positioning_terms_avoided=[],
            rationale=["user_supplied_exact_display_copy"],
            confidence=0.9,
        )
    return PositioningRealizationPlan(
        requested_positioning=requested_positioning,
        realization_mode="implicit" if requested_positioning else "balanced",
        copy_expression_policy="avoid_direct_positioning_terms",
        preferred_channels=["visual_style", "composition", "lighting", "color", "typography", "negative_space", "sensory_copy"],
        copy_should_carry_positioning=False,
        direct_positioning_terms_allowed=[],
        direct_positioning_terms_avoided=sorted(set([*requested_positioning, *direct_terms])),
        rationale=["positioning_is_visual_and_tonal_direction", "copy_should_remain_product_centered"],
        confidence=0.85,
    )


def score_native_copy_candidate(
    candidate: NativeCopyCandidate,
    *,
    product_identity: str | None,
    requested_positioning: list[str] | None = None,
    exact_user_copy: bool = False,
    campaign_message_plan: dict[str, Any] | None = None,
) -> NativeCopyScorecard:
    texts = [candidate.headline, candidate.supporting_copy or candidate.closing_copy or ""]
    joined = " ".join(texts)
    used_direct = direct_positioning_terms_used(joined)
    headline_direct = direct_positioning_terms_used(candidate.headline)
    product_norm = _norm(product_identity or "")
    headline_norm = _norm(candidate.headline)
    support_norm = _norm(candidate.supporting_copy or candidate.closing_copy or "")
    support_has_sensory_cue = _contains_sensory_cue(candidate.supporting_copy or candidate.closing_copy or "")
    product_in_headline = bool(product_norm and headline_norm and (product_norm in headline_norm or headline_norm in product_norm))
    product_anchor = product_in_headline
    duplicate = bool(support_norm and headline_norm and (support_norm in headline_norm or headline_norm in support_norm))
    direct_penalty = 0.0 if exact_user_copy else min(1.0, 0.35 * len(used_direct) + (0.25 if headline_direct else 0.0))
    generic_prestige_penalty = 0.0 if exact_user_copy else (0.35 if any(term in joined.lower() for term in ABSTRACT_PRESTIGE_TERMS) else 0.0)
    abstract_penalty = min(1.0, direct_penalty + generic_prestige_penalty)
    repetition_penalty = 0.35 if duplicate else 0.0
    unsupported_claim_penalty = 0.0
    campaign_role = str((campaign_message_plan or {}).get("campaign_role") or "")
    visible_copy_mode = str((campaign_message_plan or {}).get("visible_copy_mode") or "")
    support_expected = visible_copy_mode in {"headline_plus_support", "headline_plus_closing"}
    forced_support_penalty = 0.35 if candidate.supporting_copy and not support_expected and not candidate.support_basis_ids and candidate.support_basis_type in {"none", "aesthetic_expression"} else 0.0
    campaign_role_mismatch_penalty = 0.35 if campaign_role == "new_product_introduction" and not candidate.supporting_copy and support_expected else 0.0
    typography_dominance_mismatch_penalty = 0.25 if visible_copy_mode == "product_name_only" and candidate.supporting_copy else 0.0
    generic_launch_copy_penalty = 0.55 if contains_generic_launch_copy(candidate.supporting_copy or candidate.closing_copy or "") else 0.0
    launch_literalization_penalty = 0.45 if contains_generic_launch_copy(candidate.headline) else 0.0
    campaign_repetition_penalty = 0.35 if contains_generic_launch_copy(joined) and campaign_role == "new_product_introduction" else 0.0
    product_identity_contamination_penalty = 0.75 if contains_campaign_modifier(product_identity) or contains_campaign_modifier(candidate.headline) else 0.0
    generic_support_penalty = 0.45 if candidate.supporting_copy and (candidate.support_information_gain < 0.35 or candidate.support_product_specificity < 0.35) else 0.0
    support_information_gain_score = candidate.support_information_gain if candidate.supporting_copy else 1.0
    support_product_specificity_score = candidate.support_product_specificity if candidate.supporting_copy else 1.0
    campaign_context_subtlety_score = max(0.0, 1.0 - launch_literalization_penalty - campaign_repetition_penalty)
    headline_product_clarity_score = 0.9 if product_anchor and not contains_campaign_modifier(candidate.headline) else 0.35
    campaign_role_fit = max(0.0, min(1.0, 0.9 - campaign_role_mismatch_penalty - typography_dominance_mismatch_penalty - campaign_repetition_penalty * 0.3))
    message_density_fit = max(0.0, min(1.0, 0.9 - forced_support_penalty - typography_dominance_mismatch_penalty))
    copy_visual_contribution = 0.82 if candidate.supporting_copy or candidate.closing_copy else 0.68
    candidate_distinctiveness = 1.0
    product_centeredness = max(0.0, min(1.0, (0.9 if product_anchor else 0.45) - direct_penalty * 0.5 - generic_prestige_penalty * 0.3))
    sensory_specificity = 0.85 if candidate.sensory_terms_used or support_has_sensory_cue else (0.62 if candidate.supporting_copy else 0.55)
    evidence_grounding = 0.9 if candidate.headline_basis_ids and (not candidate.supporting_copy or candidate.support_basis_ids or candidate.sensory_terms_used or support_has_sensory_cue) else (0.72 if candidate.headline_basis_ids else 0.35)
    consumer_naturalness = max(0.0, min(1.0, 0.9 - direct_penalty * 0.35 - repetition_penalty * 0.25))
    visible_copy_naturalness_score = max(0.0, min(1.0, consumer_naturalness - generic_launch_copy_penalty * 0.3 - campaign_repetition_penalty * 0.2))
    positioning_alignment = 0.82 if requested_positioning else 0.75
    headline_strength = max(0.0, min(1.0, 0.85 if len(candidate.headline) <= 18 else 0.7))
    support_complementarity = 0.9 if candidate.supporting_copy and not duplicate and (candidate.sensory_terms_used or support_has_sensory_cue) else (0.75 if not candidate.supporting_copy else (0.62 if not duplicate else 0.45))
    restraint = max(0.0, min(1.0, 0.9 - direct_penalty * 0.55 - generic_prestige_penalty * 0.35 - repetition_penalty * 0.25 - forced_support_penalty * 0.3))
    native_fit = 0.9 if candidate.text_block_count <= 2 and candidate.total_character_count <= 48 else 0.45
    blocking_reasons: list[str] = []
    if product_centeredness < 0.55:
        blocking_reasons.append("product_centeredness_too_low")
    if not product_anchor:
        blocking_reasons.append("product_identity_missing")
    if direct_penalty >= 0.5:
        blocking_reasons.append("positioning_literalization")
    if generic_prestige_penalty > 0 and not product_anchor:
        blocking_reasons.append("abstract_copy_without_product_anchor")
    if candidate.supporting_copy and not (candidate.support_basis_ids or candidate.sensory_terms_used or support_has_sensory_cue):
        blocking_reasons.append("supporting_copy_too_abstract")
    if forced_support_penalty > 0:
        blocking_reasons.append("forced_support_without_basis")
    if campaign_role_mismatch_penalty > 0:
        blocking_reasons.append("campaign_role_copy_mode_mismatch")
    if repetition_penalty > 0:
        blocking_reasons.append("abstract_premium_repetition")
    if product_identity_contamination_penalty > 0:
        blocking_reasons.append("product_identity_contains_campaign_modifier")
    if launch_literalization_penalty > 0:
        blocking_reasons.append("launch_context_literalized_as_headline")
    if generic_launch_copy_penalty >= 0.55:
        blocking_reasons.append("generic_launch_support_detected")
    total = (
        product_centeredness * 0.18
        + sensory_specificity * 0.10
        + evidence_grounding * 0.12
        + consumer_naturalness * 0.14
        + positioning_alignment * 0.10
        + headline_strength * 0.12
        + support_complementarity * 0.10
        + restraint * 0.10
        + native_fit * 0.04
        + campaign_role_fit * 0.06
        + message_density_fit * 0.05
        + copy_visual_contribution * 0.03
        - direct_penalty * 0.12
        - generic_prestige_penalty * 0.08
        - repetition_penalty * 0.06
        - forced_support_penalty * 0.08
        - campaign_role_mismatch_penalty * 0.08
        - typography_dominance_mismatch_penalty * 0.05
        - generic_launch_copy_penalty * 0.10
        - launch_literalization_penalty * 0.08
        - campaign_repetition_penalty * 0.08
        - product_identity_contamination_penalty * 0.12
        - generic_support_penalty * 0.08
    )
    return NativeCopyScorecard(
        candidate_id=candidate.candidate_id,
        product_identity_clarity=0.9 if product_anchor else 0.4,
        product_centeredness=product_centeredness,
        sensory_specificity=sensory_specificity,
        evidence_grounding=evidence_grounding,
        consumer_naturalness=consumer_naturalness,
        positioning_alignment=positioning_alignment,
        headline_strength=headline_strength,
        support_complementarity=support_complementarity,
        restraint=restraint,
        native_typography_fit=native_fit,
        direct_positioning_penalty=direct_penalty,
        generic_prestige_penalty=generic_prestige_penalty,
        abstract_language_penalty=abstract_penalty,
        repetition_penalty=repetition_penalty,
        unsupported_claim_penalty=unsupported_claim_penalty,
        campaign_role_fit=campaign_role_fit,
        message_density_fit=message_density_fit,
        copy_visual_contribution=copy_visual_contribution,
        candidate_distinctiveness=candidate_distinctiveness,
        forced_support_penalty=forced_support_penalty,
        duplicate_candidate_penalty=0.0,
        campaign_role_mismatch_penalty=campaign_role_mismatch_penalty,
        typography_dominance_mismatch_penalty=typography_dominance_mismatch_penalty,
        support_information_gain_score=support_information_gain_score,
        support_product_specificity_score=support_product_specificity_score,
        campaign_context_subtlety_score=campaign_context_subtlety_score,
        headline_product_clarity_score=headline_product_clarity_score,
        visible_copy_naturalness_score=visible_copy_naturalness_score,
        generic_launch_copy_penalty=generic_launch_copy_penalty,
        launch_literalization_penalty=launch_literalization_penalty,
        campaign_repetition_penalty=campaign_repetition_penalty,
        product_identity_contamination_penalty=product_identity_contamination_penalty,
        generic_support_penalty=generic_support_penalty,
        total_score=max(0.0, min(1.0, total)),
        blocked=bool(blocking_reasons),
        blocking_reasons=sorted(set(blocking_reasons)),
    )


# Format profile grammar. Exactly one profile is emitted per package so a
# format's grammar never leaks into another format's prompt.
_FORMAT_PROFILE_GRAMMAR: dict[str, list[str]] = {
    "banner": [
        "- Layout grammar: Horizontal web promotion banner.",
        "- Visual composition: Split composition. Place the product on one side, and the text blocks clearly on the other side.",
        "- Two text blocks only: headline plus optional supporting copy.",
    ],
    "poster": [
        "- Layout grammar: Single centered poster hero.",
        "- Visual composition: Product is prominently centered. Text is placed cleanly above or below the product.",
        "- Two text blocks only: headline plus optional supporting copy.",
    ],
    "instagram_feed": [
        "- Layout grammar: Square Instagram feed advertisement.",
        "- Visual composition: Modern, clean text integrated smoothly into the scene.",
        "- Two approved text blocks only: headline plus optional supporting copy.",
        "- Do not invent hashtags, account names, CTA, prices, dates, badges, or social-media UI text.",
    ],
    "instagram_story": [
        "- Layout grammar: Vertical Instagram story advertisement.",
        "- Visual composition: Keep safe top and bottom breathing room. Text is centered and clean.",
        "- Two approved text blocks only: headline plus optional supporting copy.",
        "- Do not invent hashtags, account names, swipe prompts, CTA, prices, dates, badges, or social-media UI text.",
    ],
    "product_detail": [
        "- Layout grammar: E-commerce product detail section (Infographic style).",
        "- Visual composition: Show the product clearly, surrounded by clean, distinct feature label cards.",
        "- Render the approved feature labels as a 2-4 item card grid; no messy flyer blocks.",
    ],
    "flyer_editorial": [
        "- Layout grammar: Elegant editorial flyer with information layout.",
        "- Visual composition: Product integrated with 4-6 distinct, clean information text blocks structured neatly.",
        "- Calm editorial hierarchy; no promotional badge, offer, or operational contact text.",
    ],
    "flyer_promotional": [
        "- Layout grammar: Busy promotional flyer.",
        "- Visual composition: Bold product display with 7-10 distinct text blocks including promotional badges and info.",
        "- Text must be placed in clean, readable blocks around the product.",
    ],
}

_BRIEF_PROFILE_BY_FORMAT = {
    "banner": "banner",
    "poster": "poster",
    "instagram_feed": "instagram_feed",
    "instagram_story": "instagram_story",
}


def _coerce_plan_model(plan: Any, model_cls: type):
    if plan is None:
        return None
    if isinstance(plan, model_cls):
        return plan
    return model_cls(**plan)


def _resolve_prompt_profile(
    *,
    ad_format: str | None,
    copy_brief: ApprovedNativeCopyBrief,
    product_detail_plan,
    flyer_editorial_plan,
    flyer_promotional_plan,
):
    """Pick the single visible-text source + format profile for the package.

    Returns (profile, visible_texts). Extended visible text is taken only from
    the matching isolated plan; banner/poster (and any non-extended state) keep
    the two-block brief.
    """
    brief_texts = copy_brief.allowed_texts or [t for t in [copy_brief.headline, copy_brief.supporting_copy, copy_brief.closing_copy] if t]
    if product_detail_plan is not None:
        return "product_detail", list(product_detail_plan.allowed_texts)
    if flyer_editorial_plan is not None:
        return "flyer_editorial", list(flyer_editorial_plan.allowed_texts)
    if flyer_promotional_plan is not None:
        return "flyer_promotional", list(flyer_promotional_plan.allowed_texts)
    profile = _BRIEF_PROFILE_BY_FORMAT.get((ad_format or "").strip(), "poster")
    return profile, list(brief_texts)


def build_native_prompt_package(
    *,
    product_understanding: dict[str, Any],
    copy_brief: ApprovedNativeCopyBrief,
    placement: str = "restaurant_poster",
    preflight_status: str = "approved",
    input_evidence: dict[str, Any] | None = None,
    campaign_message_plan: dict[str, Any] | None = None,
    visual_semantic_cue_plan: dict[str, Any] | None = None,
    typography_dominance_plan: dict[str, Any] | None = None,
    typography_expression_plan: dict[str, Any] | None = None,
    reference_typography_analysis: dict[str, Any] | None = None,
    ad_format: str | None = None,
    product_detail_approved_feature_plan: Any = None,
    flyer_approved_copy_plan: Any = None,
    flyer_promotional_approved_copy_plan: Any = None,
) -> NativeCreativePromptPackage:
    product = str(product_understanding.get("product_name") or "product")
    format_spec = build_ad_format_spec(ad_format) if ad_format in NATIVE_TYPOGRAPHY_SUPPORTED_TEXT_FORMATS else None
    product_detail_plan = _coerce_plan_model(product_detail_approved_feature_plan, ProductDetailApprovedFeaturePlan)
    flyer_editorial_plan = _coerce_plan_model(flyer_approved_copy_plan, FlyerApprovedCopyPlan)
    flyer_promotional_plan = _coerce_plan_model(flyer_promotional_approved_copy_plan, FlyerPromotionalApprovedCopyPlan)
    profile, allowed = _resolve_prompt_profile(
        ad_format=ad_format,
        copy_brief=copy_brief,
        product_detail_plan=product_detail_plan,
        flyer_editorial_plan=flyer_editorial_plan,
        flyer_promotional_plan=flyer_promotional_plan,
    )
    forbidden = sorted(set([*copy_brief.forbidden_texts, *GENERIC_CTA_TERMS, "price", "logo", "watermark"]))
    positioning_plan = copy_brief.positioning_realization_plan or build_positioning_realization_plan(requested_positioning=copy_brief.desired_positioning).model_dump()
    avoided = positioning_plan.get("direct_positioning_terms_avoided") or sorted(DIRECT_POSITIONING_TERMS)
    campaign_plan = campaign_message_plan or copy_brief.campaign_message_plan or {}
    visual_cues = visual_semantic_cue_plan or copy_brief.visual_semantic_cue_plan or {}
    dominance = typography_dominance_plan or copy_brief.typography_dominance_plan or {}
    expression = typography_expression_plan or copy_brief.typography_expression_plan or {}
    reference_style = reference_typography_analysis or {}
    lines = [
        "Create one finished advertising image with native typography rendered inside the image.",
        "PRODUCT IDENTITY",
        f"- {product}",
        "",
        "CAMPAIGN CONTEXT - NON-DISPLAY BY DEFAULT",
        f"- role: {campaign_plan.get('campaign_role') or 'product_hero'}",
        f"- campaign status: {(input_evidence or {}).get('campaign_status') or product_understanding.get('campaign_status') or 'unknown'}",
        f"- launch visibility policy: {campaign_plan.get('launch_visibility_policy') or 'implicit'}",
        f"- visible copy mode: {campaign_plan.get('visible_copy_mode') or copy_brief.message_role}",
        f"- placement: {placement}",
        "- Campaign context describes why the advertisement is being made. Do not automatically render campaign context as text.",
        "",
        "VISIBLE COPY",
    ]
    if copy_brief.headline:
        lines.append(f'- Headline exactly: "{copy_brief.headline}"')
    support = copy_brief.supporting_copy or copy_brief.closing_copy
    if support:
        lines.append(f'- Supporting copy exactly: "{support}"')
    else:
        lines.append("- Supporting copy: none")
    direction = ", ".join((input_evidence or {}).get("desired_positioning") or product_understanding.get("desired_positioning") or []) or "clean commercial"
    semantic_cues = list(visual_cues.get("non_display_cues") or [])
    lines.extend(
        [
            "",
            "SUPPORT VALUE",
            f"- support value type: {getattr(copy_brief, 'support_value_type', None) or (copy_brief.candidate_scorecard or {}).get('support_value_type') or 'use only if it adds information over headline'}",
            "- A supporting line must have information gain over the headline.",
            "",
            "TYPOGRAPHY DOMINANCE",
            f"- headline prominence: {dominance.get('headline_prominence') or 'balanced'}",
            f"- headline scale: {dominance.get('headline_scale_intent') or 'medium'}",
            f"- support scale: {dominance.get('support_scale_intent') or ('small' if support else 'none')}",
            f"- product visual priority: {dominance.get('product_visual_priority') or 0.72}",
            "",
            "TYPOGRAPHY EXPRESSION",
            f"- expression role: {expression.get('expression_role') or 'editorial_display'}",
            f"- cultural register: {expression.get('cultural_register') or 'elegant, beautiful, and natural'}",
            f"- letterform: {expression.get('letterform_character') or 'natural Hangul typography perfectly integrated with the scene aesthetic (beautiful and highly legible, NO scary or distorted brush strokes)'}",
            f"- stroke: {expression.get('stroke_character') or 'clean and natural strokes'}",
            f"- texture: {expression.get('texture_direction') or 'texture seamlessly matches the lighting and environment'}",
            f"- integration: {expression.get('visual_integration') or 'natively integrated into the composition as if it naturally belongs there'}",
            "- Typography must feel natively integrated into the composition, not like a flat text layer pasted over the image. However, it must remain beautiful, friendly, and perfectly legible. Do NOT use horror-style or messy distorted handwriting.",
            "",
            "REFERENCE TYPOGRAPHY STYLE",
            *[f"- {item}" for item in (reference_style.get('style_summary') or expression.get('reference_style_summary') or [])[:8]],
            "- Use reference style only for letterform, hierarchy, rhythm, and integration. Do not copy reference text.",
            "",
            "NON-DISPLAY VISUAL CUES",
            *[f"- {cue}" for cue in semantic_cues[:12]],
            "- These visual semantic cues describe atmosphere and composition. Do not render them as text.",
            "",
            "VISUAL POSITIONING",
            f"- Express {direction} through restrained composition, controlled lighting, color, typography, and negative space.",
            "",
            "COMPOSITION",
            "- Keep the product as the primary visual subject.",
            "- Place copy in clean negative space without overpowering the product.",
            "",
            "FORMAT PROFILE",
            f"- FORMAT PROFILE: {profile}",
            *_FORMAT_PROFILE_GRAMMAR[profile],
            "",
            "VISIBLE BLOCKS",
            *[f'- "{block}"' for block in allowed],
            "",
            "PROHIBITED EXTRA TEXT",
            "- Render only the exact approved visible copy.",
            "- Do not render New menu, New product, Launch, Introducing, or equivalent words unless they appear in the exact approved visible copy.",
            "- Do not add slogans, CTA, labels, prices, badges, menus, pseudo text, or extra Korean text.",
            f"- Do not add these positioning words unless they are present in approved copy: {', '.join(avoided[:24])}.",
        ]
    )
    final_prompt = "\n".join(lines)
    return NativeCreativePromptPackage(
        product_description=product,
        campaign_objective=str((input_evidence or {}).get("campaign_intent") or product_understanding.get("campaign_intent") or "product_promotion"),
        composition_direction=f"Show the product clearly with clean negative space for one or two text blocks. Placement: {placement}.",
        visual_style=f"{direction} realistic commercial photography with restrained visual positioning",
        lighting_direction="natural commercial lighting",
        color_direction="harmonious brand-appropriate colors with calm background",
        typography_direction="native Hangul typography integrated into the composition; exact approved text only; no button treatment",
        product_zone="center or lower center",
        text_zone="upper or left negative space",
        approved_copy=copy_brief,
        flyer_approved_copy_plan=flyer_editorial_plan,
        flyer_promotional_approved_copy_plan=flyer_promotional_plan,
        product_detail_approved_feature_plan=product_detail_plan,
        required_elements=[product, "native typography"],
        forbidden_elements=forbidden,
        exact_allowed_texts=allowed,
        exact_forbidden_texts=forbidden,
        final_prompt=final_prompt,
        prompt_sha256=sha256_text(final_prompt),
        preflight_status=preflight_status,  # type: ignore[arg-type]
        campaign_message_plan=campaign_plan,
        visual_semantic_cue_plan=visual_cues,
        typography_dominance_plan=dominance,
        typography_expression_plan=expression,
        reference_typography_analysis=reference_style,
        target_width=format_spec.width if format_spec else None,
        target_height=format_spec.height if format_spec else None,
        native_width=format_spec.width if format_spec else None,
        native_height=format_spec.height if format_spec else None,
    )


def new_native_generation_budget(*, request_fingerprint: str) -> NativeGenerationBudget:
    return NativeGenerationBudget(request_fingerprint=request_fingerprint)


def reserve_image_call(budget: NativeGenerationBudget) -> NativeGenerationBudget:
    if budget.status in {"reserved", "in_flight", "completed", "uncertain"}:
        return budget.model_copy(update={"status": "uncertain"})
    if budget.image_calls_reserved >= 1:
        return budget.model_copy(update={"status": "uncertain"})
    return budget.model_copy(update={"image_calls_reserved": 1, "status": "reserved"})


def mark_image_call_started(budget: NativeGenerationBudget) -> NativeGenerationBudget:
    if budget.status != "reserved":
        return budget.model_copy(update={"status": "uncertain"})
    return budget.model_copy(update={"image_calls_started": 1, "status": "in_flight"})


def mark_image_call_completed(budget: NativeGenerationBudget) -> NativeGenerationBudget:
    if budget.status != "in_flight":
        return budget.model_copy(update={"status": "uncertain"})
    return budget.model_copy(update={"image_calls_completed": 1, "status": "completed"})


def request_fingerprint(payload: dict[str, Any]) -> str:
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def contains_request_intent(value: str | None) -> bool:
    return _contains_request_intent(value)


def _contains_request_intent(value: str | None) -> bool:
    return any(re.search(pattern, value or "", re.IGNORECASE) for pattern in REQUEST_INTENT_PATTERNS)


def _similarity(left: str, right: str) -> float:
    left_norm = _norm(left)
    right_norm = _norm(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    overlap = len(set(left_norm) & set(right_norm))
    return overlap / max(len(set(left_norm)), len(set(right_norm)))


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _contains_sensory_cue(value: str | None) -> bool:
    lowered = (value or "").lower()
    return any(cue.lower() in lowered for cue in SENSORY_LANGUAGE_CUES)


# --- Task 7: format-specific extended-plan isolation ---------------------------
#
# Extended visible text (flyer / product-detail) is authorized only through the
# matching isolated plan for the selected format. The two-block ApprovedNativeCopyBrief
# contract (max_text_blocks <= 2) is never weakened; banner/poster carry it alone.

_BRIEF_ONLY_FORMATS = NATIVE_TYPOGRAPHY_SUPPORTED_TEXT_FORMATS - {"flyer", "product_detail"}


def validate_flyer_approved_copy_plan(plan: Any) -> list[str]:
    """Authoritative editorial-flyer schema validation. Returns failure codes."""
    return _validate_plan(plan, FlyerApprovedCopyPlan, "flyer_approved_copy_plan_invalid")


def validate_flyer_promotional_approved_copy_plan(plan: Any) -> list[str]:
    return _validate_plan(plan, FlyerPromotionalApprovedCopyPlan, "flyer_promotional_approved_copy_plan_invalid")


def validate_product_detail_approved_feature_plan(plan: Any) -> list[str]:
    return _validate_plan(plan, ProductDetailApprovedFeaturePlan, "product_detail_approved_feature_plan_invalid")


def _validate_plan(plan: Any, model_cls: type, invalid_code: str) -> list[str]:
    if plan is None:
        return ["plan_missing"]
    if isinstance(plan, model_cls):
        return []
    try:
        model_cls(**plan)
    except (ValidationError, TypeError):
        return [invalid_code]
    return []


class VisibleTextSourceResolution(NamedTuple):
    status: str  # "ok" | "fail"
    source_kind: str | None  # "brief" | "product_detail" | "flyer_editorial" | "flyer_promotional"
    decision: str  # "approved" | "manual_review" | "rejected"
    failure_codes: list[str]


def resolve_visible_text_source_by_format(
    *,
    ad_format: str | None,
    flyer_approved_copy_plan: Any = None,
    flyer_promotional_approved_copy_plan: Any = None,
    product_detail_approved_feature_plan: Any = None,
) -> VisibleTextSourceResolution:
    """Pick the single authorized visible-text source for the format, or fail closed.

    Never resolves a conflict by precedence: any contamination, conflict, or
    missing-required plan returns an explicit failure code and a non-approved
    decision so the caller does not proceed to the prompt package / image step.
    """
    fmt = (ad_format or "").strip()
    has_editorial = flyer_approved_copy_plan is not None
    has_promo = flyer_promotional_approved_copy_plan is not None
    has_product_detail = product_detail_approved_feature_plan is not None

    if fmt in _BRIEF_ONLY_FORMATS or fmt == "":
        codes: list[str] = []
        if has_editorial or has_promo or has_product_detail:
            codes.append("extended_plan_not_allowed_for_format")
        if codes:
            return VisibleTextSourceResolution("fail", None, "rejected", codes)
        return VisibleTextSourceResolution("ok", "brief", "approved", [])

    if fmt == "product_detail":
        if has_editorial or has_promo:
            codes = ["flyer_plan_used_for_product_detail"]
            if has_product_detail:
                codes.append("conflicting_extended_plans")
            return VisibleTextSourceResolution("fail", None, "rejected", codes)
        if not has_product_detail:
            return VisibleTextSourceResolution("fail", None, "manual_review", ["missing_required_extended_plan"])
        failures = validate_product_detail_approved_feature_plan(product_detail_approved_feature_plan)
        if failures:
            return VisibleTextSourceResolution("fail", None, "rejected", failures)
        return VisibleTextSourceResolution("ok", "product_detail", "approved", [])

    if fmt == "flyer":
        if has_product_detail:
            codes = ["product_detail_plan_used_for_flyer"]
            if has_editorial or has_promo:
                codes.append("conflicting_extended_plans")
            return VisibleTextSourceResolution("fail", None, "rejected", codes)
        if has_editorial and has_promo:
            return VisibleTextSourceResolution("fail", None, "rejected", ["multiple_flyer_plans_present"])
        if not (has_editorial or has_promo):
            return VisibleTextSourceResolution("fail", None, "manual_review", ["missing_required_extended_plan"])
        if has_editorial:
            failures = validate_flyer_approved_copy_plan(flyer_approved_copy_plan)
            if failures:
                return VisibleTextSourceResolution("fail", None, "rejected", failures)
            return VisibleTextSourceResolution("ok", "flyer_editorial", "approved", [])
        failures = validate_flyer_promotional_approved_copy_plan(flyer_promotional_approved_copy_plan)
        if failures:
            return VisibleTextSourceResolution("fail", None, "rejected", failures)
        return VisibleTextSourceResolution("ok", "flyer_promotional", "approved", [])

    # Unknown/unsupported format must not carry any extended plan.
    if has_editorial or has_promo or has_product_detail:
        return VisibleTextSourceResolution("fail", None, "rejected", ["extended_plan_not_allowed_for_format"])
    return VisibleTextSourceResolution("ok", "brief", "approved", [])
