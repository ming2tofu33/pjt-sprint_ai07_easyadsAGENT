from orchestrator.app.graph.nodes import resolve_copy_generation_mode
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, CopyModeInferenceOutput, CopywritingOutput, InitialMarketingRequest, MarketingCopy
from orchestrator.app.schemas.text_layout import ImagePromptSpec


def _state(user_plan: str = "premium"):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            user_plan=user_plan,
            copy_generation_mode="auto_pilot",
            context={
                "business_type": "restaurant",
                "item_or_service": "BBQ",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        )
    )
    state.update(format_planner_node(state))
    state.update({"marketing_copy": MarketingCopy(headline="Hello BBQ", subcopy="Sub", cta="Book").model_dump()})
    state.update(text_style_binder_node(state))
    state.update({"copy_spec": {"items": [{"role": "headline", "text": "Hello BBQ"}], "copy_mode": "standard", "tone_profile": {}}})
    state.update(text_layout_planner_node(state))
    return state


def test_copy_mode_inference_disabled_falls_back_to_missing():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ambiguous request", user_plan="premium"))
    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    assert mode is None
    assert output is None
    assert state["llm_call_results"]
    assert state["llm_call_results"][0]["error"] == "api_call_disabled"


def test_copy_mode_inference_adapter_output_can_be_used(monkeypatch):
    expected = CopyModeInferenceOutput(copy_generation_mode="no_copy", confidence=0.9, source="heuristic")
    monkeypatch.setattr("orchestrator.app.graph.nodes.run_structured_node", lambda *args, **kwargs: (expected, {"fallback_used": False}))
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ambiguous request", user_plan="premium"))

    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    assert mode == "no_copy"
    assert output.copy_generation_mode == "no_copy"


def test_copy_candidates_disabled_uses_rule_fallback():
    state = _state("premium")
    output = copy_candidate_generation_node(state)

    assert len(output["copy_candidates"]) == 3
    assert output["llm_call_results"][0]["error"] == "api_call_disabled"
    assert all("010-" not in candidate["headline"] for candidate in output["copy_candidates"])


def test_copy_candidates_adapter_success_is_used(monkeypatch):
    llm_output = CopyCandidateListOutput(
        candidates=[CopyCandidate(id="x", headline="LLM headline", subcopy="LLM sub", cta="Go")],
        recommended_candidate_id="x",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.copy_candidates.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    output = copy_candidate_generation_node(_state("premium"))

    assert output["copy_candidates"][0]["headline"] == "LLM headline"


def test_auto_pilot_disabled_uses_rule_fallback():
    output = auto_pilot_copywriting_node(_state("premium"))

    assert output["marketing_copy"]["headline"]
    assert output["llm_call_results"][0]["error"] == "api_call_disabled"


def test_auto_pilot_adapter_success_is_used(monkeypatch):
    copy = MarketingCopy(headline="LLM copy", subcopy="LLM sub", cta="Act")
    llm_output = CopywritingOutput(marketing_copy=copy)
    monkeypatch.setattr("orchestrator.app.llm.nodes.auto_pilot_copywriting.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    output = auto_pilot_copywriting_node(_state("premium"))

    assert output["marketing_copy"]["headline"] == "LLM copy"


def test_image_prompt_planner_disabled_keeps_safety_fields():
    state = _state("premium")
    output = image_prompt_planner_node(state)

    spec = output["image_prompt_spec"]
    assert spec["must_not_include_text"] is True
    assert spec["reserved_text_areas"] == state["text_layout_spec"]["reserved_text_areas"]
    assert "hangul" in spec["negative_prompt_en"].lower()
    assert output["llm_call_results"] == []
    assert spec["metadata"]["prompt_critic"]["fallback_used"] is True


def test_image_prompt_planner_adapter_success_is_safety_corrected(monkeypatch):
    unsafe = ImagePromptSpec(
        scene_description="scene",
        product_subject="BBQ",
        color_palette=[],
        composition="composition",
        lighting="lighting",
        reserved_text_areas=[],
        must_not_include_text=False,
        positive_prompt_en="positive",
        negative_prompt_en="low quality",
        target_width=1,
        target_height=1,
        aspect_ratio="1:1",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.image_prompt_planner.run_structured_node", lambda *args, **kwargs: (unsafe, {"fallback_used": False}))
    state = _state("premium")
    output = image_prompt_planner_node(state)

    spec = output["image_prompt_spec"]
    assert spec["must_not_include_text"] is True
    assert spec["reserved_text_areas"] == state["text_layout_spec"]["reserved_text_areas"]
    assert spec["target_width"] == state["ad_format_spec"]["width"]
    assert "watermark" in spec["negative_prompt_en"].lower()
