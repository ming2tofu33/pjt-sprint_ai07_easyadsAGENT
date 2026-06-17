import inspect

from orchestrator.app.graph.nodes import options_node, state_update_node, validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.brief_interpreter import (
    build_context_updates_from_brief_interpreter,
    interpret_brief_with_llm,
)
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.prompt_renderer import prompt_renderer_node
from orchestrator.app.llm.nodes.result import result_node
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.tone_binding import tone_binding_node
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext, ToneBindingOutput


def _state(**kwargs):
    defaults = {
        "user_input": "Need a premium ad",
        "user_plan": "premium",
        "requested_ad_format": "instagram_feed",
        "copy_generation_mode": "auto_pilot",
    }
    defaults.update(kwargs)
    return create_initial_marketing_state(InitialMarketingRequest(**defaults))


def test_brief_interpreter_disabled_does_not_call_runner(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("brief interpreter should not call LLM by default")

    monkeypatch.setattr("orchestrator.app.llm.nodes.brief_interpreter.run_structured_node", fail_if_called)
    output, metadata = interpret_brief_with_llm(_state(), "ambiguous request")

    assert output is None
    assert metadata["fallback_reason"] == "brief_interpreter_not_enabled"
    assert called is False


def test_validator_merges_valid_brief_interpreter_output_without_promoting_closed_business_literal(monkeypatch):
    llm_output = BriefInterpreterOutput(
        business_type="cafe",
        item_or_service="Strawberry latte",
        promotion_goal="new_launch",
        target_persona="office workers",
        tone="premium",
        copy_generation_mode="suggest_candidates",
        confidence=0.9,
    )
    monkeypatch.setattr("orchestrator.app.graph.nodes.interpret_brief_with_llm", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    state = _state(copy_generation_mode=None)

    result = validator_node(state)

    assert result["context"]["business_type"] is None
    assert result["context"]["item_or_service"] == "Strawberry latte"
    assert result["context"]["promotion_goal"] == "new_launch"
    assert result["context"]["target_persona"] == "office workers"
    assert result["context"]["brand_tone"] == "premium"
    assert result["copy_generation_mode"] == "suggest_candidates"
    assert result["copy_mode_inference_output"]["source"] == "brief_interpreter_llm"
    assert result["copy_mode_inference_output"]["metadata"]["source"] == "brief_interpreter_llm"
    assert "business_type" in result["missing_fields"]
    assert result["validator_metadata"]["brief_interpreter"]["used"] is True


def test_validator_does_not_overwrite_explicit_context(monkeypatch):
    llm_output = BriefInterpreterOutput(
        business_type="cafe",
        item_or_service="Latte",
        promotion_goal="new_launch",
        tone="cute",
        confidence=0.9,
    )
    monkeypatch.setattr("orchestrator.app.graph.nodes.interpret_brief_with_llm", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    state = _state(context=MarketingContext(business_type="restaurant", item_or_service="BBQ", promotion_goal="reservation_cta"))

    result = validator_node(state)

    assert result["context"]["business_type"] == "restaurant"
    assert result["context"]["item_or_service"] == "BBQ"
    assert result["context"]["promotion_goal"] == "reservation_cta"


def test_user_provided_discount_or_location_is_not_treated_as_invented_fact():
    output = BriefInterpreterOutput(
        business_type="cafe",
        item_or_service="Mango bingsu",
        target_persona="Gangnam office workers",
        promotion_goal="discount_event",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(
        output,
        source_text="Gangnam office workers cafe ad for Mango bingsu 30% discount",
    )

    assert updates["business_type"] == "cafe"
    assert updates["item_or_service"] == "Mango bingsu"
    assert updates["target_persona"] == "Gangnam office workers"
    assert updates["promotion_goal"] == "discount_event"
    assert not warnings


def test_romanized_item_recovered_from_korean_source():
    # LLM romanized/translated the Korean product noun; recover the user's Korean term.
    output = BriefInterpreterOutput(
        business_type="retail",
        item_or_service="doljabi_ring",
        promotion_goal="discount_event",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(
        output,
        source_text="돌잡이 반지 할인 이벤트",
    )

    assert updates["item_or_service"] == "돌잡이 반지"
    assert any("recovered from source" in w for w in warnings)


def test_retail_business_type_is_preserved_from_brief_interpreter():
    output = BriefInterpreterOutput(
        business_type="retail",
        item_or_service="돌반지",
        promotion_goal="discount_event",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(
        output,
        source_text="돌반지 할인 이벤트",
    )

    assert updates["business_type"] == "retail"
    assert updates["item_or_service"] == "돌반지"
    assert updates["promotion_goal"] == "discount_event"
    assert not any("business_type_fallback_generic" in warning for warning in warnings)


def test_validator_turns_ambiguous_beauty_domain_into_business_type_question(monkeypatch):
    llm_output = BriefInterpreterOutput(
        business_type="beauty",
        item_or_service="시카 세럼",
        promotion_goal="reservation",
        tone="premium",
        confidence=0.9,
    )
    monkeypatch.setattr(
        "orchestrator.app.graph.nodes.interpret_brief_with_llm",
        lambda *args, **kwargs: (llm_output, {"fallback_used": False}),
    )

    result = validator_node(_state())

    assert result["context"]["business_type"] is None
    assert "business_type" in result["missing_fields"]
    assert any(
        "business_type_fallback_generic: ambiguous_beauty_subdomain" in warning
        for warning in result["validator_metadata"]["brief_interpreter"]["warnings"]
    )


def test_validator_keeps_generic_fallback_business_literal_out_of_public_context(monkeypatch):
    llm_output = BriefInterpreterOutput(
        business_type="education",
        item_or_service="영어 회화반",
        promotion_goal="reservation",
        tone="friendly",
        confidence=0.9,
    )
    monkeypatch.setattr(
        "orchestrator.app.graph.nodes.interpret_brief_with_llm",
        lambda *args, **kwargs: (llm_output, {"fallback_used": False}),
    )

    result = validator_node(_state())

    assert result["context"]["business_type"] is None
    assert "business_type" in result["missing_fields"]
    assert any(
        "business_type_fallback_generic: unsupported_domain_in_mvp" in warning
        for warning in result["validator_metadata"]["brief_interpreter"]["warnings"]
    )


def test_korean_item_kept_when_not_romanized():
    output = BriefInterpreterOutput(
        business_type="retail",
        item_or_service="돌반지",
        promotion_goal="discount_event",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(
        output,
        source_text="돌반지 할인",
    )

    assert updates["item_or_service"] == "돌반지"
    assert updates["business_type"] == "retail"
    assert not any("item_or_service" in w or "recovered" in w for w in warnings)


def test_unprovided_phone_or_discount_is_blocked_as_invented_fact():
    output = BriefInterpreterOutput(
        business_type="restaurant",
        item_or_service="BBQ 010-1234-5678",
        target_persona="30% discount seekers",
        promotion_goal="reservation",
        confidence=0.95,
    )

    updates, warnings = build_context_updates_from_brief_interpreter(output, source_text="BBQ reservation ad")

    assert updates["business_type"] == "restaurant"
    assert updates["promotion_goal"] == "reservation_cta"
    assert "item_or_service" not in updates
    assert "target_persona" not in updates
    assert warnings


def test_low_confidence_brief_interpreter_output_is_ignored(monkeypatch):
    llm_output = BriefInterpreterOutput(business_type="cafe", confidence=0.2)
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setattr("orchestrator.app.llm.nodes.brief_interpreter.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))

    output, metadata = interpret_brief_with_llm(_state(), "ambiguous request")

    assert output is None
    assert metadata["fallback_reason"] == "low_brief_interpreter_confidence"


def test_tone_binding_rejects_business_incompatible_tone(monkeypatch):
    llm_output = ToneBindingOutput(
        tone_profile="medical_clinical_skin",
        recommended_copy_mode="auto_pilot",
        copy_constraints=[],
        forbidden_claims=[],
        channel_copy_rules=[],
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.tone_binding.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    state = _state(context=MarketingContext(business_type="cafe", item_or_service="Latte", promotion_goal="new_launch"))

    result = tone_binding_node(state)

    assert result["tone_binding_output"]["tone_profile"] != "medical_clinical_skin"
    assert result["tone_binding_output"]["metadata"]["llm_metadata"]["fallback_reason"] == "business_incompatible_tone_binding"


def test_selected_deterministic_nodes_do_not_use_structured_llm_runner():
    nodes = [
        options_node,
        state_update_node,
        format_planner_node,
        prompt_renderer_node,
        text_layout_planner_node,
        t2i_request_builder_node,
        text_renderer_node,
        result_node,
    ]

    for node in nodes:
        assert "run_structured_node" not in inspect.getsource(node)
