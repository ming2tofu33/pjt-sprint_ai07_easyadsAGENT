"""Tests for P7-2/P7-3 option suggester LLM node and state update integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.types import Command

from orchestrator.app.core.config import _get_env
from orchestrator.app.graph.builder import build_intake_graph
from orchestrator.app.graph.nodes import display_value_for_selection, options_node, state_update_node
from orchestrator.app.graph.state import MarketingState
from orchestrator.app.llm.nodes.option_suggester import (
    build_option_suggester_prompt,
    should_attempt_option_suggester,
    suggest_options,
)
from orchestrator.app.llm.option_registry import get_option_question
from orchestrator.app.llm.settings import get_llm_settings
from orchestrator.app.schemas.option_suggestion import OptionSuggestionItem, OptionSuggestionOutput


# --- Gating Tests ---

@pytest.fixture
def mock_llm_settings():
    with patch("orchestrator.app.llm.nodes.option_suggester.get_llm_settings") as mock_get:
        settings = MagicMock()
        settings.enable_api_call = True
        settings.local_llm_base_url = None
        settings.local_llm_model = None
        mock_get.return_value = settings
        yield settings


def test_should_attempt_gating_paid(mock_llm_settings):
    state = {"user_plan": "economic"}
    assert should_attempt_option_suggester(state) is True


def test_should_attempt_gating_free_no_local(mock_llm_settings):
    state = {"user_plan": "free"}
    assert should_attempt_option_suggester(state) is False


def test_should_attempt_gating_free_with_local(mock_llm_settings, monkeypatch):
    monkeypatch.setenv("EASYADS_FREE_USE_LOCAL", "1")
    mock_llm_settings.local_llm_base_url = "http://localhost:8000/v1"
    mock_llm_settings.local_llm_model = "gemma-2b"
    state = {"user_plan": "free"}
    assert should_attempt_option_suggester(state) is True


# --- suggest_options Tests ---

@patch("orchestrator.app.llm.nodes.option_suggester.run_structured_node")
@patch("orchestrator.app.llm.nodes.option_suggester.should_attempt_option_suggester")
def test_suggest_options_returns_items(mock_should, mock_run):
    mock_should.return_value = True
    state = {"user_plan": "economic", "user_input": "Test input"}
    question = get_option_question("item_or_service")
    
    mock_output = OptionSuggestionOutput(
        options=[
            OptionSuggestionItem(label="다이나믹 1", value="dynamic_1"),
            OptionSuggestionItem(label="다이나믹 2", value="dynamic_2"),
        ],
        confidence=0.8
    )
    mock_run.return_value = (mock_output, {"model": "test-model"})
    
    output, metadata = suggest_options(state, "item_or_service", question)
    assert output is not None
    assert output.confidence == 0.8
    assert len(output.options) == 2


@patch("orchestrator.app.llm.nodes.option_suggester.run_structured_node")
@patch("orchestrator.app.llm.nodes.option_suggester.should_attempt_option_suggester")
def test_suggest_options_low_confidence_still_returns_output_but_meta_is_valid(mock_should, mock_run):
    # Note: `suggest_options` just returns what the LLM gave. Confidence checking happens in `_augment_options`.
    mock_should.return_value = True
    state = {"user_plan": "economic"}
    question = get_option_question("item_or_service")
    
    mock_output = OptionSuggestionOutput(
        options=[],
        confidence=0.3
    )
    mock_run.return_value = (mock_output, {"model": "test-model"})
    
    output, metadata = suggest_options(state, "item_or_service", question)
    assert output is not None
    assert output.confidence == 0.3


@patch("orchestrator.app.llm.nodes.option_suggester.should_attempt_option_suggester")
def test_suggest_options_llm_off_returns_none(mock_should):
    mock_should.return_value = False
    state = {"user_plan": "free"}
    question = get_option_question("item_or_service")
    
    output, metadata = suggest_options(state, "item_or_service", question)
    assert output is None
    assert metadata["fallback_used"] is True


# --- Graph & Nodes Tests ---

@patch("orchestrator.app.graph.nodes._augment_options")
def test_options_node_eligible_augmented(mock_augment):
    # We invoke the graph with an eligible missing field
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-123"}}
    
    question = get_option_question("item_or_service")
    from orchestrator.app.schemas.llm_marketing import OptionItem
    mock_augment.return_value = [
        OptionItem(id=1, label="다이나믹 1", value="dynamic_1"),
        OptionItem(id=2, label="직접 입력", value="custom")
    ]
    
    # We supply missing_fields manually by constructing a state that goes to options
    result = graph.invoke({
        "schema_version": "1.0",
        "job_id": "job-123",
        "user_input": "Test",
        "thread_id": "thread-123",
        "missing_fields": ["item_or_service"], # Force item_or_service first
        "context": {"business_type": "restaurant"},
        "status": "validating_context",
    }, config=config)
    
    # It should interrupt
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "option_question"
    
    q = interrupt_payload["option_question"]
    assert q["field"] == "item_or_service"
    
    # Check that dynamic option was merged in
    labels = [opt["label"] for opt in q["options"]]
    assert "다이나믹 1" in labels
    
    # Verify custom is still last
    assert q["options"][-1]["value"] == "custom"


@patch("orchestrator.app.graph.nodes._augment_options")
def test_options_node_enum_unchanged(mock_augment):
    # Not eligible fields like `ad_format` or `copy_generation_mode`
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-456"}}
    
    # Even if mock was called (it shouldn't be), the graph shouldn't use it
    # Full required context so copy_generation_mode is the only missing field asked
    # (otherwise validator re-adds eligible fields and one gets asked first).
    result = graph.invoke({
        "user_input": "Test",
        "thread_id": "thread-456",
        "missing_fields": ["copy_generation_mode"],
        "context": {
            "business_type": "restaurant",
            "item_or_service": "대표 메뉴",
            "promotion_goal": "discount_event",
            "extra": {"ad_format": "instagram_feed"},
        },
        "status": "validating_context",
    }, config=config)

    interrupt_payload = result["__interrupt__"][0].value
    q = interrupt_payload["option_question"]
    assert q["field"] == "copy_generation_mode"
    
    # mock_augment should not have been called because is_field_eligible("copy_generation_mode") == False
    mock_augment.assert_not_called()


@patch("orchestrator.app.graph.nodes._augment_options")
def test_options_node_cached_stable(mock_augment):
    # If there are cached options in current_brief, the LLM is not called again
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-789"}}
    
    cached_options_dict = {
        "item_or_service": [
            {"id": 1, "label": "대표 메뉴", "value": "signature_item"},
            {"id": 2, "label": "캐시된 다이나믹", "value": "cached_dynamic"},
            {"id": 3, "label": "직접 입력", "value": "custom"},
        ]
    }
    
    # Build a real pass-through state (schema_version + job_id) so input_node
    # preserves current_brief.cached_options instead of rebuilding from scratch.
    # Full required context except item_or_service → item_or_service asked first,
    # cache used, no _augment_options call.
    from orchestrator.app.graph.state import create_initial_marketing_state
    from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest

    state = create_initial_marketing_state(
        InitialMarketingRequest(user_input="Test", thread_id="thread-789")
    )
    state["context"] = {
        "business_type": "restaurant",
        "promotion_goal": "discount_event",
        "extra": {"ad_format": "instagram_feed"},
    }
    state["missing_fields"] = ["item_or_service"]
    state["current_brief"] = {**state.get("current_brief", {}), "cached_options": cached_options_dict}
    result = graph.invoke(state, config=config)
    
    interrupt_payload = result["__interrupt__"][0].value
    q = interrupt_payload["option_question"]
    labels = [opt["label"] for opt in q["options"]]
    
    assert "캐시된 다이나믹" in labels
    mock_augment.assert_not_called()


def test_state_update_dynamic_label_resolved():
    # If a user selects a dynamic value for item_or_service, state_update_node resolves the label
    state = {
        "user_selection": {
            "job_id": "j1", "thread_id": "t1",
            "field": "item_or_service", "value": "dynamic_1"
        },
        "job_id": "j1", "thread_id": "t1",
        "current_brief": {
            "cached_options": {
                "item_or_service": [
                    {"id": 1, "label": "다이나믹 레이블", "value": "dynamic_1"}
                ]
            }
        },
        "context": {"business_type": "restaurant"},
        "missing_fields": ["item_or_service", "promotion_goal"]
    }
    
    res = state_update_node(state)
    
    assert res["status"] == "updating_state"
    assert res["context"]["item_or_service"] == "다이나믹 레이블" # The resolved label
    assert res["context"]["extra"]["item_or_service_option_value"] == "dynamic_1" # Stashed slug
    assert "item_or_service" not in res["missing_fields"]


def test_state_update_promotion_goal_slug_passthrough():
    # promotion_goal is NOT in DISPLAY_LABEL_CONTEXT_FIELDS, so the slug is kept
    state = {
        "user_selection": {
            "job_id": "j1", "thread_id": "t1",
            "field": "promotion_goal", "value": "dynamic_goal"
        },
        "job_id": "j1", "thread_id": "t1",
        "current_brief": {
            "cached_options": {
                "promotion_goal": [
                    {"id": 1, "label": "골 레이블", "value": "dynamic_goal"}
                ]
            }
        },
        "context": {"business_type": "restaurant"},
        "missing_fields": ["promotion_goal"]
    }
    
    res = state_update_node(state)
    
    assert res["context"]["promotion_goal"] == "dynamic_goal" # Raw slug preserved
    assert "promotion_goal_option_value" not in res["context"]["extra"] # Nothing stashed


def test_options_node_cached_path_preserves_current_brief_and_skips_llm_tracking():
    state: MarketingState = {
        "job_id": "job-1",
        "thread_id": "thread-1",
        "status": "validating_context",
        "missing_fields": ["item_or_service"],
        "context": {"business_type": "restaurant"},
        "current_brief": {
            "sentinel": "keep",
            "cached_options": {
                "item_or_service": [
                    {"id": 1, "label": "cached option", "value": "cached_dynamic"},
                    {"id": 2, "label": "custom", "value": "custom"},
                ]
            },
        },
    }

    with patch("orchestrator.app.graph.nodes.interrupt", lambda payload: payload):
        update = options_node(state)

    assert update["current_brief"]["sentinel"] == "keep"
    assert update["option_question"]["options"][0]["value"] == "cached_dynamic"
    assert "model_selections" not in update
    assert "llm_call_results" not in update
