"""Guarded prompt critic helper for ImagePrompt v3 drafts."""

from __future__ import annotations

import hashlib
from typing import Any

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.metadata_builders import metadata_contract_to_prompt_json
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.schemas.prompt_critic import PromptCriticOutput


SUPPORTED_PROMPT_CRITIC_ENGINES = {"gpt_image_2", "sd35_large", "flux"}


def critique_prompt_draft(
    state: MarketingState | dict[str, Any],
    *,
    prompt_draft: str,
    target_engine: str,
    prompt_context: dict[str, Any],
) -> tuple[PromptCriticOutput | None, dict[str, Any]]:
    if not should_attempt_prompt_critic(state, prompt_draft=prompt_draft, target_engine=target_engine):
        return None, {
            "enabled": False,
            "attempted": False,
            "fallback_used": True,
            "fallback_reason": "prompt_critic_not_enabled",
        }
    metadata = build_prompt_critic_metadata(prompt_draft=prompt_draft, target_engine=target_engine, prompt_context=prompt_context)
    output, llm_metadata = run_structured_node(
        state,
        node_name="prompt_critic",
        output_schema=PromptCriticOutput,
        prompt=build_prompt_critic_prompt(prompt_draft=prompt_draft, target_engine=target_engine, prompt_context=prompt_context, metadata=metadata),
        fallback_fn=lambda: None,
        risk_level="medium",
        confidence=0.5,
        latency_budget="standard",
        metadata=metadata,
    )
    if not isinstance(output, PromptCriticOutput):
        return None, {**llm_metadata, "fallback_used": True, "fallback_reason": "invalid_prompt_critic_output"}
    if output.confidence < 0.6:
        return None, {**llm_metadata, "fallback_used": True, "fallback_reason": "low_prompt_critic_confidence"}
    return output, llm_metadata


def should_attempt_prompt_critic(state: MarketingState | dict[str, Any], *, prompt_draft: str, target_engine: str) -> bool:
    if not prompt_draft.strip():
        return False
    if (target_engine or "").lower() not in SUPPORTED_PROMPT_CRITIC_ENGINES:
        return False
    if state.get("user_plan", "free") == "free":
        return False
    settings = get_llm_settings()
    if not settings.enable_api_call:
        return False
    selection = choose_model(
        node_name="prompt_critic",
        user_plan=state.get("user_plan", "free"),
        confidence=0.5,
        risk_level="medium",
        latency_budget="standard",
        plan_policy=state.get("plan_policy"),
    )
    return selection.provider != "mock"


def build_prompt_critic_metadata(*, prompt_draft: str, target_engine: str, prompt_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": "prompt_critic",
        "target_engine": target_engine,
        "prompt_draft_present": bool(prompt_draft),
        "prompt_draft_length": len(prompt_draft),
        "prompt_draft_hash": hashlib.sha256(prompt_draft.encode("utf-8")).hexdigest()[:16] if prompt_draft else None,
        "business_type": prompt_context.get("business_type"),
        "business_subtype": prompt_context.get("business_subtype"),
        "ad_format": prompt_context.get("ad_format"),
        "promotion_goal": prompt_context.get("promotion_goal"),
        "business_visual_preset_id": prompt_context.get("business_visual_preset_id"),
        "selected_reference_template_id": prompt_context.get("selected_reference_template_id"),
        "render_text_in_image": False,
        "constraints": {
            "no_text": True,
            "no_logo": True,
            "no_signage": True,
            "reserved_negative_space": True,
        },
    }


def build_prompt_critic_prompt(*, prompt_draft: str, target_engine: str, prompt_context: dict[str, Any], metadata: dict[str, Any]) -> str:
    return (
        "You are reviewing an image-generation prompt draft for a commercial advertising background. "
        "Return structured PromptCriticOutput only. Do not directly produce or modify ImagePromptSpec. "
        "Preserve no readable text in image, no Korean letters, no logos, no signage, no prices, "
        "no phone numbers, no addresses, reserved clean negative space for later copy overlay, "
        "business type and subtype, and reference template alignment. "
        "Only suggest improvements to subject hierarchy, commercial realism, business fit, lighting, "
        "composition, material realism, negative space, clutter reduction, and model-specific phrasing. "
        "Do not weaken any safety or no-text constraint. "
        # quality_score/confidence는 스키마가 [0,1] float인데 모델이 0-10으로 줘 le=1.0 위반→매 premium 런 폐기됐다.
        # 스케일 명시로 conform 유도(스키마/extra=forbid 안전 가드는 그대로). fix.md #16.
        "quality_score and confidence MUST each be a decimal float between 0.0 and 1.0 "
        "(for example 0.82), never a 0-10 or 0-100 score. "
        f"Target engine: {target_engine}. "
        f"Prompt context: {metadata_contract_to_prompt_json(metadata)}. "
        f"Prompt draft: {prompt_draft[:1800]}"
    )
