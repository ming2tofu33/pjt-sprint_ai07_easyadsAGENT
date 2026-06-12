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
    return sorted(set(failures))


def build_native_prompt_package(
    *,
    product_understanding: dict[str, Any],
    copy_brief: ApprovedNativeCopyBrief,
    placement: str = "restaurant_poster",
    preflight_status: str = "approved",
) -> NativeCreativePromptPackage:
    product = str(product_understanding.get("product_name") or "product")
    allowed = copy_brief.allowed_texts or [text for text in [copy_brief.headline, copy_brief.supporting_copy, copy_brief.closing_copy] if text]
    forbidden = sorted(set([*copy_brief.forbidden_texts, *GENERIC_CTA_TERMS, "price", "logo", "watermark"]))
    lines = [
        "Create one finished Korean restaurant poster image with native typography rendered inside the image.",
        f"Product: {product}. Placement: {placement}.",
        "Only render the exact approved Korean text below. Do not add any other letters, numbers, logos, watermarks, price, buttons, badges, menus, or pseudo text.",
    ]
    if copy_brief.headline:
        lines.append(f'Headline text exactly: "{copy_brief.headline}"')
    support = copy_brief.supporting_copy or copy_brief.closing_copy
    if support:
        lines.append(f'Supporting text exactly: "{support}"')
    lines.append("Use warm premium food photography, clean composition, readable Hangul typography, and keep text away from the main dish.")
    final_prompt = "\n".join(lines)
    return NativeCreativePromptPackage(
        product_description=product,
        campaign_objective="menu promotion",
        composition_direction="Hero doenjang jjigae dish with clean negative space for one or two text blocks.",
        visual_style="premium realistic Korean restaurant poster",
        lighting_direction="warm natural restaurant lighting",
        color_direction="warm earthy soup tones with calm neutral background",
        typography_direction="native Hangul typography, exact approved text only, no button treatment",
        product_zone="center or lower center",
        text_zone="upper or left negative space",
        approved_copy=copy_brief,
        required_elements=["doenjang jjigae", "warm bowl", "native typography"],
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
