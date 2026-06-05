"""Deterministic resolver for prompt critic rewrite proposals."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from orchestrator.app.schemas.prompt_critic import PromptCriticOutput


NO_TEXT_FRAGMENTS = [
    "no readable text",
    "no Korean letters",
    "no logos",
    "no signage",
    "no watermark",
    "no typography",
    "no menu text",
    "no price tags",
    "clean reserved negative space for later copy overlay",
]

FORBIDDEN_POSITIVE_TERMS = [
    "readable text",
    "korean letters",
    "typography",
    "logo",
    "brand name",
    "signage",
    "menu text",
    "price tag",
    "watermark",
    "caption",
    "poster text",
    "label text",
    "store sign",
    "phone number",
    "address",
]

ALLOWED_REWRITE_HINTS = [
    "lighting",
    "composition",
    "subject",
    "hierarchy",
    "commercial",
    "realistic",
    "realism",
    "negative space",
    "copy overlay",
    "uncluttered",
    "clean",
    "background",
    "texture",
    "material",
    "depth of field",
    "color",
    "props",
    "premium",
    "photography",
]

UNSAFE_LITERAL_PATTERNS = [
    re.compile(r"[가-힣]"),
    re.compile(r"\b010[-\s]?\d{3,4}[-\s]?\d{4}\b"),
    re.compile(r"\b\d{2,3}[-\s]?\d{3,4}[-\s]?\d{4}\b"),
    re.compile(r"\d+\s*%"),
    re.compile(r"(?:₩|\$)\s*\d+"),
    re.compile(r"\d{1,3}(?:,\d{3})+\s*(?:원|krw|price)?", re.IGNORECASE),
    re.compile(r"(?:주소|전화|연락처|영업시간|할인율|discount|phone|address)", re.IGNORECASE),
]


@dataclass(frozen=True)
class PromptRewriteResolution:
    prompt: str
    rewrite_applied: bool = False
    rejected_change_codes: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None


def resolve_prompt_rewrite(
    original_prompt: str,
    critic_output: PromptCriticOutput | None,
    prompt_context: dict[str, Any] | None = None,
    *,
    quality_policy: Any | None = None,
    max_length: int = 2200,
) -> PromptRewriteResolution:
    prompt_context = prompt_context or {}
    if not critic_output:
        return _fallback(original_prompt, "prompt_critic_not_available")
    if critic_output.confidence < 0.6:
        return _fallback(original_prompt, "prompt_critic_low_confidence")
    if not (critic_output.preserve_no_text_policy and critic_output.preserve_reference_alignment and critic_output.preserve_business_context):
        return _fallback(original_prompt, "prompt_critic_policy_not_preserved", ["immutable_policy_violation"])
    if any(issue.severity == "critical" and issue.code == "unsafe_rewrite_request" for issue in critic_output.issues):
        return _fallback(original_prompt, "prompt_critic_safety_rejected", ["unsafe_rewrite_request"])

    prompt = original_prompt
    rejected: list[str] = []
    applied = False
    rewrite = critic_output.rewrite

    for old, new in rewrite.replace_fragments.items():
        if _touches_protected_context(old, prompt_context):
            rejected.append("replace_protected_context_rejected")
            continue
        if old and old in prompt and _is_allowed_fragment(new, prompt_context):
            prompt = prompt.replace(old, new)
            applied = True
        elif old or new:
            rejected.append("replace_rejected")

    for fragment in rewrite.remove_fragments:
        if _touches_protected_context(fragment, prompt_context):
            rejected.append("remove_protected_context_rejected")
            continue
        if fragment and fragment in prompt and _is_removable_fragment(fragment):
            prompt = prompt.replace(fragment, "")
            applied = True
        elif fragment:
            rejected.append("remove_rejected")

    for fragment in rewrite.add_fragments[:8]:
        if _is_allowed_fragment(fragment, prompt_context):
            if fragment not in prompt:
                prompt = f"{prompt.rstrip()} {fragment.strip()}"
                applied = True
        elif fragment:
            rejected.append("add_rejected")

    if rewrite.rewritten_prompt:
        rejected.append("rewritten_prompt_direct_apply_blocked")

    prompt = enforce_no_text_constraints(prompt)
    policy_valid, policy_reason = validate_rewritten_prompt_policy(prompt, quality_policy)
    if not policy_valid:
        return _fallback(original_prompt, policy_reason or "prompt_quality_policy_rejected", [*rejected, "prompt_quality_policy_rejected"])
    if len(prompt) > max_length:
        return _fallback(original_prompt, "prompt_critic_prompt_too_long", [*rejected, "prompt_too_long"])
    return PromptRewriteResolution(prompt=prompt, rewrite_applied=applied, rejected_change_codes=rejected)


def validate_rewritten_prompt_policy(prompt: str, quality_policy: Any | None) -> tuple[bool, str | None]:
    if not quality_policy:
        return True, None
    lowered = prompt.lower()
    if "negative space" not in lowered and "copy overlay" not in lowered:
        return False, "prompt_quality_policy_missing_safe_area"
    if any(pattern.search(prompt) for pattern in UNSAFE_LITERAL_PATTERNS):
        return False, "prompt_quality_policy_unsafe_literal"
    return True, None


def enforce_no_text_constraints(prompt: str) -> str:
    result = (prompt or "").strip()
    for fragment in NO_TEXT_FRAGMENTS:
        if fragment.lower() not in result.lower():
            result = f"{result} {fragment}."
    return result.strip()


def _is_allowed_fragment(fragment: str, prompt_context: dict[str, Any]) -> bool:
    text = (fragment or "").strip()
    lowered = text.lower()
    if not text:
        return False
    if any(term in lowered for term in FORBIDDEN_POSITIVE_TERMS):
        return False
    if any(key in lowered for key in ["render_text_in_image", "business_type", "selectedreferencetemplateid", "selected_reference_template_id"]):
        return False
    if any(pattern.search(text) for pattern in UNSAFE_LITERAL_PATTERNS):
        return False
    if _touches_protected_context(text, prompt_context):
        return False
    return any(hint in lowered for hint in ALLOWED_REWRITE_HINTS)


def _is_removable_fragment(fragment: str) -> bool:
    lowered = fragment.lower()
    return not any(term in lowered for term in ["text", "logo", "signage", "watermark", "negative space", "copy overlay"])


def _fallback(original_prompt: str, reason: str, rejected: list[str] | None = None) -> PromptRewriteResolution:
    return PromptRewriteResolution(
        prompt=enforce_no_text_constraints(original_prompt),
        rewrite_applied=False,
        rejected_change_codes=rejected or [],
        fallback_used=True,
        fallback_reason=reason,
    )


def _normalize(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _protected_context_values(prompt_context: dict[str, Any]) -> list[str]:
    values = [
        prompt_context.get("business_type"),
        prompt_context.get("business_subtype"),
        prompt_context.get("item_or_service"),
        prompt_context.get("primary_subject"),
        prompt_context.get("selected_reference_template_id"),
    ]
    return [_normalize(value) for value in values if _normalize(value)]


def _touches_protected_context(fragment: str, prompt_context: dict[str, Any]) -> bool:
    normalized_fragment = _normalize(fragment)
    return any(protected in normalized_fragment for protected in _protected_context_values(prompt_context))
