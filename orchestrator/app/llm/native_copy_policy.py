"""Deterministic policy for GPT Image 2 native typography lane."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from orchestrator.app.schemas.native_creative import (
    ApprovedNativeCopyBrief,
    CreativeExecutionPlan,
    NativeCreativePromptPackage,
    NativeGenerationBudget,
    NativeTypographyEligibilityDecision,
    NativeCopyCandidate,
    NativeCopyScorecard,
    PositioningRealizationPlan,
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
        if source_request and brief.headline and _contains_request_intent(source_request) and _similarity(source_request, brief.headline) >= 0.75:
            failures.append("user_request_copied_as_headline")
    if not set(brief.product_evidence_ids or brief.verified_evidence_ids):
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
            language=brief.language,
            text_block_count=min(len(texts) or 1, 2),
            total_character_count=sum(len(text) for text in texts),
        ),
        product_identity=brief.product_identity,
        requested_positioning=brief.desired_positioning,
        exact_user_copy=brief.copy_source_mode == "user_exact",
    )
    if score.blocked:
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
) -> NativeCopyScorecard:
    texts = [candidate.headline, candidate.supporting_copy or candidate.closing_copy or ""]
    joined = " ".join(texts)
    used_direct = direct_positioning_terms_used(joined)
    headline_direct = direct_positioning_terms_used(candidate.headline)
    product_norm = _norm(product_identity or "")
    headline_norm = _norm(candidate.headline)
    support_norm = _norm(candidate.supporting_copy or candidate.closing_copy or "")
    support_has_sensory_cue = _contains_sensory_cue(candidate.supporting_copy or candidate.closing_copy or "")
    product_in_headline = bool(product_norm and product_norm in headline_norm)
    product_anchor = product_in_headline or candidate.strategy in {"minimal_identity", "product_name_first", "product_attribute_first"}
    duplicate = bool(support_norm and headline_norm and (support_norm in headline_norm or headline_norm in support_norm))
    direct_penalty = 0.0 if exact_user_copy else min(1.0, 0.35 * len(used_direct) + (0.25 if headline_direct else 0.0))
    generic_prestige_penalty = 0.0 if exact_user_copy else (0.35 if any(term in joined.lower() for term in ABSTRACT_PRESTIGE_TERMS) else 0.0)
    abstract_penalty = min(1.0, direct_penalty + generic_prestige_penalty)
    repetition_penalty = 0.35 if duplicate else 0.0
    unsupported_claim_penalty = 0.0
    product_centeredness = max(0.0, min(1.0, (0.9 if product_anchor else 0.45) - direct_penalty * 0.5 - generic_prestige_penalty * 0.3))
    sensory_specificity = 0.85 if candidate.sensory_terms_used or support_has_sensory_cue else (0.62 if candidate.supporting_copy else 0.55)
    evidence_grounding = 0.9 if candidate.headline_basis_ids and (not candidate.supporting_copy or candidate.support_basis_ids or candidate.sensory_terms_used or support_has_sensory_cue) else (0.72 if candidate.headline_basis_ids else 0.35)
    consumer_naturalness = max(0.0, min(1.0, 0.9 - direct_penalty * 0.35 - repetition_penalty * 0.25))
    positioning_alignment = 0.82 if requested_positioning else 0.75
    headline_strength = max(0.0, min(1.0, 0.85 if len(candidate.headline) <= 18 else 0.7))
    support_complementarity = 0.9 if candidate.supporting_copy and not duplicate and (candidate.sensory_terms_used or support_has_sensory_cue) else (0.75 if not candidate.supporting_copy else (0.62 if not duplicate else 0.45))
    restraint = max(0.0, min(1.0, 0.9 - direct_penalty * 0.55 - generic_prestige_penalty * 0.35 - repetition_penalty * 0.25))
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
    if repetition_penalty > 0:
        blocking_reasons.append("abstract_premium_repetition")
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
        - direct_penalty * 0.12
        - generic_prestige_penalty * 0.08
        - repetition_penalty * 0.06
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
        total_score=max(0.0, min(1.0, total)),
        blocked=bool(blocking_reasons),
        blocking_reasons=sorted(set(blocking_reasons)),
    )


def build_native_prompt_package(
    *,
    product_understanding: dict[str, Any],
    copy_brief: ApprovedNativeCopyBrief,
    placement: str = "restaurant_poster",
    preflight_status: str = "approved",
    input_evidence: dict[str, Any] | None = None,
) -> NativeCreativePromptPackage:
    product = str(product_understanding.get("product_name") or "product")
    allowed = copy_brief.allowed_texts or [text for text in [copy_brief.headline, copy_brief.supporting_copy, copy_brief.closing_copy] if text]
    forbidden = sorted(set([*copy_brief.forbidden_texts, *GENERIC_CTA_TERMS, "price", "logo", "watermark"]))
    positioning_plan = copy_brief.positioning_realization_plan or build_positioning_realization_plan(requested_positioning=copy_brief.desired_positioning).model_dump()
    avoided = positioning_plan.get("direct_positioning_terms_avoided") or sorted(DIRECT_POSITIONING_TERMS)
    lines = [
        "Create one finished advertising image with native typography rendered inside the image.",
        f"Product: {product}. Placement: {placement}.",
        "Only render the exact approved Korean text below. Do not add any other letters, numbers, logos, watermarks, price, buttons, badges, menus, or pseudo text.",
    ]
    if copy_brief.headline:
        lines.append(f'Headline text exactly: "{copy_brief.headline}"')
    support = copy_brief.supporting_copy or copy_brief.closing_copy
    if support:
        lines.append(f'Supporting text exactly: "{support}"')
    direction = ", ".join((input_evidence or {}).get("desired_positioning") or product_understanding.get("desired_positioning") or []) or "clean commercial"
    lines.append("COPY DIRECTION: Use only the approved product-centered headline and support. Do not add positioning words not present in approved copy.")
    lines.append(f"VISUAL POSITIONING DIRECTION: Express {direction} through restrained composition, controlled lighting, color, typography, and negative space.")
    lines.append(f"Do not add these words unless they are present in approved copy: {', '.join(avoided[:24])}.")
    final_prompt = "\n".join(lines)
    return NativeCreativePromptPackage(
        product_description=product,
        campaign_objective=str((input_evidence or {}).get("campaign_intent") or product_understanding.get("campaign_intent") or "product_promotion"),
        composition_direction=f"Show the product clearly with clean negative space for one or two text blocks. Placement: {placement}.",
        visual_style=f"{direction} realistic commercial photography with restrained visual positioning",
        lighting_direction="natural commercial lighting",
        color_direction="harmonious brand-appropriate colors with calm background",
        typography_direction="native Hangul typography, exact approved text only, no button treatment",
        product_zone="center or lower center",
        text_zone="upper or left negative space",
        approved_copy=copy_brief,
        required_elements=[product, "native typography"],
        forbidden_elements=forbidden,
        exact_allowed_texts=allowed,
        exact_forbidden_texts=forbidden,
        final_prompt=final_prompt,
        prompt_sha256=sha256_text(final_prompt),
        preflight_status=preflight_status,  # type: ignore[arg-type]
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
