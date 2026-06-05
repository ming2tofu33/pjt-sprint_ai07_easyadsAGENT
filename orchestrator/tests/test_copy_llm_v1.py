from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.node_runner import append_llm_call_result
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_validation_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, InitialMarketingRequest, MarketingContext
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


def _state(user_plan: str = "premium", mode: str = "suggest_candidates"):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="딸기 케이크 신메뉴 광고",
            user_plan=user_plan,
            copy_generation_mode=mode,
            context=MarketingContext(
                business_type="cafe",
                item_or_service="딸기 케이크",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )


def test_copy_candidates_disabled_uses_rule_based_fallback():
    update = copy_candidate_generation_node(_state("premium"))

    assert update["copy_candidates"]
    assert update["llm_call_results"][0]["error"] == "api_call_disabled"


def test_copy_candidates_provider_mock_uses_rule_based_fallback(monkeypatch):
    selection = ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class="local_quality",
        provider="mock",
        structured_output=True,
        reason="forced mock provider",
    )
    monkeypatch.setattr("orchestrator.app.llm.node_runner.choose_model", lambda *args, **kwargs: selection)
    monkeypatch.setattr(
        "orchestrator.app.llm.node_runner.get_llm_adapter_safe",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("adapter should not be called")),
    )
    state = {"user_plan": "premium"}

    output, metadata = run_structured_node(
        state,
        node_name="copy_candidate_generation",
        output_schema=CopyCandidateListOutput,
        prompt="prompt",
        fallback_fn=lambda: CopyCandidateListOutput(candidates=[CopyCandidate(id="copy_1", headline="fallback")]),
    )

    assert output.candidates[0].headline == "fallback"
    assert metadata["fallback_reason"] == "provider_mock_fallback"
    assert state["llm_call_results"][0]["error"] == "provider_mock_fallback"


def test_copy_candidate_llm_valid_output_converts_to_candidate_shape(monkeypatch):
    llm_output = CopyCandidateListOutput(
        candidates=[CopyCandidate(id="x", headline="딸기 케이크 신메뉴", subcopy="오늘 만나는 달콤함", cta="메뉴 보기")],
        recommended_candidate_id="x",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.copy_candidates.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))

    update = copy_candidate_generation_node(_state("premium"))

    assert update["copy_candidates"][0]["id"] == "x"
    assert update["copy_candidates"][0]["headline"] == "딸기 케이크 신메뉴"
    assert update["copy_candidates"][0]["metadata"]["copy_tone_policy"]["policy_id"] == "cafe_v1"


def test_copy_candidate_hallucinated_phone_or_discount_falls_back(monkeypatch):
    unsafe = CopyCandidateListOutput(
        candidates=[CopyCandidate(id="x", headline="딸기 케이크 50% 할인", subcopy="010-1234-5678로 주문", cta="전화하기")],
        recommended_candidate_id="x",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.copy_candidates.run_structured_node", lambda *args, **kwargs: (unsafe, {"fallback_used": False}))

    update = copy_candidate_generation_node(_state("premium"))
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "010-1234-5678" not in rendered
    assert "50%" not in rendered
    assert update["copywriting_output"]["metadata"]["llm_metadata"]["fallback_reason"] == "llm_candidate_validation_failed"


def test_custom_input_is_not_rewritten():
    state = _state("premium", mode="custom_input")
    state["user_custom_headline"] = "망고빙수 30% 할인"
    state["user_custom_subcopy"] = "이번 주 한정"

    update = custom_copy_validation_node(state)

    assert update["marketing_copy"]["headline"] == "망고빙수 30% 할인"
    assert update["marketing_copy"]["subcopy"] == "이번 주 한정"
    assert update["marketing_copy"]["metadata"]["preserved_user_copy"] is True


def test_llm_call_results_store_summary_without_raw_text_or_output():
    state = {}
    selection = ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class="local_quality",
        provider="local_openai_compat",
        structured_output=True,
        reason="test",
        model_name="gemma4-e4b",
        provider_profile="local_gemma_e4b",
    )
    append_llm_call_result(
        state,
        LLMCallResult(
            success=True,
            node_name="copy_candidate_generation",
            model_selection=selection,
            output={"candidates": [{"headline": "raw output should not be stored"}]},
            raw_text="raw response should not be stored",
            metadata={"api_key": "sk-secret", "safe": True},
        ),
    )

    dumped = str(state["llm_call_results"])
    assert "raw response should not be stored" not in dumped
    assert "raw output should not be stored" not in dumped
    assert "sk-secret" not in dumped
    assert state["llm_call_results"][0]["raw_text_present"] is True
    assert state["llm_call_results"][0]["output_candidate_count"] == 1


def test_free_auto_pilot_uses_deterministic_fallback_not_actual_llm():
    update = auto_pilot_copywriting_node(_state("free", mode="auto_pilot"))

    assert update["marketing_copy"]["headline"]
    assert update["llm_call_results"][0]["error"] == "free_plan_deterministic_fallback"
