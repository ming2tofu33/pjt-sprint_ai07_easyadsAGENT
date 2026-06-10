"""Default plan policy construction for LLM-capable nodes."""

from __future__ import annotations

from typing import get_args

from orchestrator.app.schemas.llm_model_policy import ModelClass, NodeModelName, NodeModelPolicy, PlanPolicy, UserPlan


ALL_MODEL_CLASSES: list[ModelClass] = list(get_args(ModelClass))
API_MODEL_CLASSES = {"api_nano", "api_mini", "api_full", "api_vision"}


def normalize_user_plan(value: str | None) -> UserPlan:
    if value in {"free", "economic", "premium", "internal_benchmark"}:
        return value  # type: ignore[return-value]
    return "free"


def build_default_plan_policy(user_plan: UserPlan | str) -> PlanPolicy:
    plan = normalize_user_plan(str(user_plan) if user_plan is not None else None)
    if plan == "free":
        allowed: list[ModelClass] = ["local_fast", "local_quality", "mock"]
        max_api_calls = 0
        max_candidates = 2
        vision_gate = False
        allow_api_fallback = False
    elif plan == "economic":
        allowed = ["local_fast", "local_quality", "api_nano", "api_mini", "mock"]
        max_api_calls = 3
        max_candidates = 3
        vision_gate = False
        allow_api_fallback = True
    elif plan == "premium":
        allowed = ["local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"]
        max_api_calls = 10
        max_candidates = 5
        vision_gate = True
        allow_api_fallback = True
    else:
        allowed = ["local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"]
        max_api_calls = 999
        max_candidates = 5
        vision_gate = True
        allow_api_fallback = True
    return PlanPolicy(
        user_plan=plan,
        allowed_model_classes=allowed,
        max_api_calls_per_job=max_api_calls,
        max_candidates=max_candidates,
        vision_gate_enabled=vision_gate,
        allow_api_fallback=allow_api_fallback,
        node_policies=get_default_node_policies(plan),
        metadata={
            "source": "default_plan_policy",
            "local_fast_max_calls": 2 if plan == "free" else None,
            "local_quality_max_calls": 1 if plan == "free" else None,
            "auto_pilot_copywriting": "merged_with_copy_candidate_generation" if plan == "free" else "separate_node",
            "prompt_optimization": "conditional" if plan == "free" else "standard",
        },
    )


def get_default_node_policies(user_plan: UserPlan | str) -> dict[str, NodeModelPolicy]:
    plan = normalize_user_plan(str(user_plan) if user_plan is not None else None)
    allowed_by_plan = build_allowed_model_classes(plan)
    defaults = default_model_class_by_node(plan)
    policies: dict[str, NodeModelPolicy] = {}
    for node_name, default_model in defaults.items():
        node_allowed = allowed_for_node(node_name, allowed_by_plan, default_model)
        policies[node_name] = NodeModelPolicy(
            node_name=node_name,
            default_model_class=default_model if default_model in node_allowed else node_allowed[0],
            allowed_model_classes=node_allowed,
            requires_structured_output=True,
            vision_required=node_name in {"background_validation"} and plan in {"premium", "internal_benchmark"},
            fallback_model_class="mock",
            max_retries=0,
            timeout_seconds=8 if node_name in {"validator", "copy_mode_inference"} else 20,
        )
    return policies


def build_allowed_model_classes(plan: UserPlan) -> list[ModelClass]:
    if plan == "free":
        return ["local_fast", "local_quality", "mock"]
    if plan == "economic":
        return ["local_fast", "local_quality", "api_nano", "api_mini", "mock"]
    return ["local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"]


def default_model_class_by_node(plan: UserPlan) -> dict[NodeModelName, ModelClass]:
    if plan == "free":
        return {
            "validator": "local_fast",
            "copy_mode_inference": "local_fast",
            "tone_binding": "mock",
            "copy_candidate_generation": "local_quality",
            "copy_generation_v2_actual": "local_quality",
            "copy_candidate_rank_v2": "local_quality",
            "copy_visual_intent": "local_fast",
            "auto_pilot_copywriting": "local_quality",
            "custom_copy_validation": "local_fast",
            "copy_spec_parser": "local_fast",
            "image_prompt_planner": "local_quality",
            "prompt_critic": "mock",
            "background_validation": "mock",
            "final_validation": "mock",
            "revision_intent_classifier": "local_fast",
        }
    if plan == "economic":
        return {
            "validator": "local_fast",
            "copy_mode_inference": "local_fast",
            "tone_binding": "local_fast",
            "copy_candidate_generation": "api_nano",
            "copy_generation_v2_actual": "api_mini",
            "copy_candidate_rank_v2": "api_mini",
            "copy_visual_intent": "api_nano",
            "auto_pilot_copywriting": "api_nano",
            "custom_copy_validation": "local_fast",
            "copy_spec_parser": "local_fast",
            "image_prompt_planner": "api_nano",
            "prompt_critic": "api_mini",
            "background_validation": "mock",
            "final_validation": "api_nano",
            "revision_intent_classifier": "api_nano",
        }
    if plan == "premium":
        return {
            "validator": "api_nano",
            "copy_mode_inference": "api_mini",
            "tone_binding": "api_nano",
            "copy_candidate_generation": "api_mini",
            "copy_generation_v2_actual": "api_mini",
            "copy_candidate_rank_v2": "api_mini",
            "copy_visual_intent": "api_mini",
            "auto_pilot_copywriting": "api_mini",
            "custom_copy_validation": "api_mini",
            "copy_spec_parser": "api_nano",
            "image_prompt_planner": "api_full",
            "prompt_critic": "api_mini",
            "background_validation": "api_vision",
            "final_validation": "api_mini",
            "revision_intent_classifier": "api_mini",
        }
    return {
        "validator": "api_full",
        "copy_mode_inference": "api_full",
        "tone_binding": "api_mini",
        "copy_candidate_generation": "api_full",
        "copy_generation_v2_actual": "api_mini",
        "copy_candidate_rank_v2": "api_mini",
        "copy_visual_intent": "api_mini",
        "auto_pilot_copywriting": "api_full",
        "custom_copy_validation": "api_mini",
        "copy_spec_parser": "api_mini",
        "image_prompt_planner": "api_full",
        "prompt_critic": "api_full",
        "background_validation": "api_vision",
        "final_validation": "api_vision",
        "revision_intent_classifier": "api_mini",
    }


def allowed_for_node(node_name: NodeModelName, plan_allowed: list[ModelClass], default_model: ModelClass) -> list[ModelClass]:
    allowed = list(plan_allowed)
    if node_name in {"background_validation", "final_validation"} and "api_vision" in allowed:
        return allowed
    if default_model not in allowed:
        allowed.insert(0, default_model)
    return [model for model in allowed if model in plan_allowed or model == "mock"]
