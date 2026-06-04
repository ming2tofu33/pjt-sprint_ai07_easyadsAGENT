from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_marketing import CopyModeInferenceOutput


def _state(plan: str = "premium"):
    from orchestrator.app.graph.state import create_initial_marketing_state
    from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest

    return create_initial_marketing_state(InitialMarketingRequest(user_input="ready", user_plan=plan))


def test_node_runner_disabled_uses_fallback_and_tracks_result():
    state = _state("premium")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt should not be stored",
        fallback_fn=lambda: CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=0.7, source="heuristic"),
        settings=LLMSettings(enable_api_call=False),
    )

    assert output.copy_generation_mode == "auto_pilot"
    assert metadata["fallback_used"] is True
    assert state["model_selections"]
    assert state["llm_call_results"][0]["error"] == "api_call_disabled"
    assert "prompt should not be stored" not in str(state["llm_call_results"])


def test_node_runner_free_plan_uses_fallback():
    state = _state("free")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt",
        fallback_fn=lambda: None,
        settings=LLMSettings(enable_api_call=True),
    )

    assert output is None
    assert metadata["fallback_reason"] == "free_plan_deterministic_fallback"


def test_node_runner_invalid_structured_output_falls_back(monkeypatch):
    class BadAdapter:
        def invoke_structured(self, schema, prompt, model_selection, metadata=None):
            from orchestrator.app.schemas.llm_model_policy import LLMCallResult

            return LLMCallResult(success=True, node_name=model_selection.node_name, model_selection=model_selection, output={"bad": True})

    monkeypatch.setattr("orchestrator.app.llm.node_runner.get_llm_adapter_safe", lambda *args, **kwargs: BadAdapter())
    state = _state("premium")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt",
        fallback_fn=lambda: CopyModeInferenceOutput(copy_generation_mode="suggest_candidates", confidence=0.8, source="heuristic"),
        settings=LLMSettings(enable_api_call=True, openai_api_key="set", openai_text_model_mini="model"),
    )

    assert output.copy_generation_mode == "suggest_candidates"
    assert metadata["fallback_reason"] == "structured_output_validation_failed"
