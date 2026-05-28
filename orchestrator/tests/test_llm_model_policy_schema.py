from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.llm_model_policy import (
    LLMCallResult,
    ModelClass,
    ModelSelection,
    NodeModelPolicy,
    PlanPolicy,
    UserPlan,
)


def test_model_policy_literals_include_expected_values():
    assert set(get_args(UserPlan)) == {"free", "economic", "premium", "internal_benchmark"}
    assert set(get_args(ModelClass)) == {"local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"}


def test_node_model_policy_validates_allowed_defaults():
    policy = NodeModelPolicy(node_name="validator", default_model_class="local_fast", allowed_model_classes=["local_fast", "mock"])
    assert policy.fallback_model_class == "mock"

    with pytest.raises(ValidationError):
        NodeModelPolicy(node_name="validator", default_model_class="api_full", allowed_model_classes=["local_fast"])


def test_plan_policy_free_blocks_api_classes():
    with pytest.raises(ValidationError):
        PlanPolicy(
            user_plan="free",
            allowed_model_classes=["local_fast", "api_nano", "mock"],
            max_api_calls_per_job=0,
            max_candidates=1,
            vision_gate_enabled=False,
            allow_api_fallback=False,
            node_policies={},
        )


def test_model_selection_and_call_result_validate():
    selection = ModelSelection(
        node_name="validator",
        user_plan="free",
        selected_model_class="mock",
        provider="mock",
        structured_output=True,
        reason="free plan uses mock",
        confidence=0.5,
    )
    result = LLMCallResult(success=True, node_name="validator", model_selection=selection, output={"ok": True})
    assert result.success is True

    with pytest.raises(ValidationError):
        ModelSelection(
            node_name="validator",
            user_plan="free",
            selected_model_class="mock",
            provider="mock",
            structured_output=True,
            reason="",
        )
    with pytest.raises(ValidationError):
        ModelSelection(
            node_name="validator",
            user_plan="free",
            selected_model_class="mock",
            provider="mock",
            structured_output=True,
            reason="bad confidence",
            confidence=2.0,
        )
