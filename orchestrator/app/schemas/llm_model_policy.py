"""Model policy schemas for future LLM-backed LangGraph nodes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


UserPlan = Literal["free", "economic", "premium", "internal_benchmark"]
ModelClass = Literal["local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"]
NodeModelName = Literal[
    "validator",
    "product_understanding",
    "copy_mode_inference",
    "tone_binding",
    "copy_candidate_generation",
    "copy_generation_v2_actual",
    "copy_candidate_rank_v2",
    "copy_visual_intent",
    "auto_pilot_copywriting",
    "custom_copy_validation",
    "copy_spec_parser",
    "image_prompt_planner",
    "prompt_critic",
    "background_validation",
    "final_validation",
    "native_creative_preflight_review",
    "revision_intent_classifier",
    "option_suggester",
]
RiskLevel = Literal["low", "medium", "high"]
LatencyBudget = Literal["interactive", "standard", "batch"]
AdapterProvider = Literal["mock", "openai", "openai_compatible", "local_openai_compat", "local_gemma", "local_qwen", "vision_api"]
CostTier = Literal["none", "low", "medium", "high"]


class NodeModelPolicy(BaseModel):
    node_name: NodeModelName
    default_model_class: ModelClass
    allowed_model_classes: list[ModelClass]
    requires_structured_output: bool = True
    vision_required: bool = False
    allow_fallback: bool = True
    fallback_model_class: ModelClass = "mock"
    max_retries: int = Field(default=0, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_model_classes(self):
        if self.default_model_class not in self.allowed_model_classes:
            raise ValueError("default_model_class must be in allowed_model_classes")
        if self.fallback_model_class != "mock" and self.fallback_model_class not in self.allowed_model_classes:
            raise ValueError("fallback_model_class must be allowed or mock")
        return self


class PlanPolicy(BaseModel):
    user_plan: UserPlan
    allowed_model_classes: list[ModelClass]
    max_api_calls_per_job: int = Field(..., ge=0)
    max_candidates: int = Field(..., ge=1)
    vision_gate_enabled: bool
    allow_api_fallback: bool
    node_policies: dict[str, NodeModelPolicy]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_plan_limits(self):
        api_classes = {"api_nano", "api_mini", "api_full", "api_vision"}
        if self.user_plan == "free":
            if api_classes & set(self.allowed_model_classes):
                raise ValueError("free plan cannot allow api model classes")
            if self.max_api_calls_per_job != 0:
                raise ValueError("free plan max_api_calls_per_job must be 0")
        return self


class ModelSelection(BaseModel):
    node_name: str
    user_plan: UserPlan
    selected_model_class: ModelClass
    provider: AdapterProvider
    structured_output: bool
    fallback_used: bool = False
    reason: str
    risk_level: RiskLevel | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_budget: LatencyBudget | None = None
    estimated_cost_tier: CostTier = "none"
    model_name: str | None = None
    provider_profile: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must not be empty")
        return value


class LLMCallResult(BaseModel):
    success: bool
    node_name: str
    model_selection: ModelSelection
    output: dict[str, Any] | str | None
    raw_text: str | None = None
    error: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] | None = None
    cost_estimate: float | None = Field(default=None, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
