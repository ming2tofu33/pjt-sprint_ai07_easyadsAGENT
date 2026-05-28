"""Model selection policy router for future LLM nodes."""

from __future__ import annotations

from typing import Any

from orchestrator.app.llm.plan_policy import build_default_plan_policy, normalize_user_plan
from orchestrator.app.schemas.llm_model_policy import AdapterProvider, LatencyBudget, ModelClass, ModelSelection, PlanPolicy, RiskLevel, UserPlan


def choose_model(
    node_name: str,
    user_plan: UserPlan | str,
    confidence: float | None = None,
    risk_level: RiskLevel | str | None = None,
    latency_budget: LatencyBudget | str | None = None,
    vision_required: bool | None = None,
    plan_policy: PlanPolicy | dict[str, Any] | None = None,
) -> ModelSelection:
    normalized_plan = normalize_user_plan(str(user_plan) if user_plan is not None else None)
    policy = normalize_plan_policy(plan_policy, normalized_plan)
    node_policy = policy.node_policies.get(node_name)
    risk = normalize_risk_level(risk_level)
    latency = normalize_latency_budget(latency_budget)

    fallback_used = False
    reason_parts: list[str] = []
    if node_policy is None:
        selected = unknown_node_fallback(normalized_plan, policy)
        structured_output = True
        fallback_used = True
        reason_parts.append(f"unknown node {node_name} used safe fallback")
    else:
        structured_output = node_policy.requires_structured_output
        selected = node_policy.default_model_class
        reason_parts.append(f"{normalized_plan} plan default for {node_name}")
        if vision_required or node_policy.vision_required:
            selected = select_for_vision(normalized_plan, policy, node_policy.allowed_model_classes)
            reason_parts.append("vision requirement considered")
        elif normalized_plan == "economic" and (confidence is not None and confidence < 0.6 or risk == "high"):
            selected = first_allowed(["api_mini", "api_nano", "local_quality", "local_fast", "mock"], node_policy.allowed_model_classes, policy.allowed_model_classes)
            reason_parts.append("economic plan escalated for low confidence or high risk")
        elif normalized_plan == "premium":
            selected = select_for_premium(node_name, latency, node_policy.allowed_model_classes, policy.allowed_model_classes)
            reason_parts.append("premium plan quality policy applied")

    if selected not in policy.allowed_model_classes:
        selected = first_allowed(["mock", "local_fast", "local_quality"], policy.allowed_model_classes, policy.allowed_model_classes)
        fallback_used = True
        reason_parts.append("selection adjusted to plan allowed classes")

    if normalized_plan == "free" and selected.startswith("api_"):
        selected = first_allowed(["local_fast", "local_quality", "mock"], policy.allowed_model_classes, policy.allowed_model_classes)
        fallback_used = True
        reason_parts.append("free plan blocks API model classes")
    if normalized_plan == "economic" and selected in {"api_full", "api_vision"}:
        selected = first_allowed(["api_mini", "api_nano", "local_fast", "mock"], policy.allowed_model_classes, policy.allowed_model_classes)
        fallback_used = True
        reason_parts.append("economic plan blocks api_full/api_vision")

    return ModelSelection(
        node_name=node_name,
        user_plan=normalized_plan,
        selected_model_class=selected,
        provider=provider_for_model_class(selected),
        structured_output=structured_output,
        fallback_used=fallback_used,
        reason="; ".join(reason_parts),
        risk_level=risk,
        confidence=confidence,
        latency_budget=latency,
        estimated_cost_tier=cost_tier_for_model_class(selected),
        metadata={"vision_required": bool(vision_required), "policy_source": policy.metadata.get("source")},
    )


def normalize_plan_policy(plan_policy: PlanPolicy | dict[str, Any] | None, user_plan: UserPlan) -> PlanPolicy:
    if plan_policy is None:
        return build_default_plan_policy(user_plan)
    if isinstance(plan_policy, PlanPolicy):
        return plan_policy
    return PlanPolicy(**plan_policy)


def normalize_risk_level(value: RiskLevel | str | None) -> RiskLevel | None:
    if value in {"low", "medium", "high"}:
        return value  # type: ignore[return-value]
    return None


def normalize_latency_budget(value: LatencyBudget | str | None) -> LatencyBudget | None:
    if value in {"interactive", "standard", "batch"}:
        return value  # type: ignore[return-value]
    return None


def unknown_node_fallback(user_plan: UserPlan, policy: PlanPolicy) -> ModelClass:
    if user_plan == "economic":
        return first_allowed(["local_fast", "mock"], policy.allowed_model_classes, policy.allowed_model_classes)
    if user_plan == "premium":
        return first_allowed(["api_nano", "mock"], policy.allowed_model_classes, policy.allowed_model_classes)
    return "mock"


def select_for_vision(user_plan: UserPlan, policy: PlanPolicy, node_allowed: list[ModelClass]) -> ModelClass:
    if user_plan in {"premium", "internal_benchmark"}:
        return first_allowed(["api_vision", "api_mini", "mock"], node_allowed, policy.allowed_model_classes)
    if user_plan == "economic":
        return first_allowed(["api_nano", "mock", "local_fast"], node_allowed, policy.allowed_model_classes)
    return first_allowed(["mock", "local_fast"], node_allowed, policy.allowed_model_classes)


def select_for_premium(node_name: str, latency: LatencyBudget | None, node_allowed: list[ModelClass], plan_allowed: list[ModelClass]) -> ModelClass:
    if latency == "interactive":
        return first_allowed(["api_mini", "api_nano", "local_fast", "mock"], node_allowed, plan_allowed)
    if node_name in {"image_prompt_planner", "auto_pilot_copywriting", "copy_candidate_generation"}:
        return first_allowed(["api_full", "api_mini", "api_nano", "mock"], node_allowed, plan_allowed)
    if node_name in {"background_validation", "final_validation"}:
        return first_allowed(["api_vision", "api_mini", "api_nano", "mock"], node_allowed, plan_allowed)
    return first_allowed(["api_mini", "api_nano", "mock"], node_allowed, plan_allowed)


def first_allowed(preferred: list[ModelClass], node_allowed: list[ModelClass], plan_allowed: list[ModelClass]) -> ModelClass:
    for model_class in preferred:
        if model_class in node_allowed and model_class in plan_allowed:
            return model_class
    for model_class in node_allowed:
        if model_class in plan_allowed:
            return model_class
    return "mock"


def provider_for_model_class(model_class: ModelClass) -> AdapterProvider:
    if model_class == "mock":
        return "mock"
    if model_class in {"local_fast", "local_quality"}:
        return "local_gemma"
    if model_class in {"api_nano", "api_mini", "api_full"}:
        return "openai"
    return "vision_api"


def cost_tier_for_model_class(model_class: ModelClass) -> str:
    if model_class in {"mock", "local_fast", "local_quality"}:
        return "none"
    if model_class in {"api_nano", "api_mini"}:
        return "low"
    if model_class == "api_full":
        return "medium"
    return "high"
