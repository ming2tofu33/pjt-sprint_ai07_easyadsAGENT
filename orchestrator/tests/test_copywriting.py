"""Consolidated tests (real physical merge of source files).

Merged from:
- orchestrator/tests/test_copy_candidates_branch.py
- orchestrator/tests/test_copy_generation_mode_options.py
- orchestrator/tests/test_copy_generation_mode_schema.py
- orchestrator/tests/test_copy_grounding_visual_intent.py
- orchestrator/tests/test_copy_llm_v1.py
- orchestrator/tests/test_copy_mode_inference.py
- orchestrator/tests/test_copy_mode_router.py
- orchestrator/tests/test_copy_quality.py
- orchestrator/tests/test_copy_quality_actual_batch_script.py
- orchestrator/tests/test_copy_quality_v2.py
- orchestrator/tests/test_copy_spec_parser_node.py
- orchestrator/tests/test_copy_tone.py
- orchestrator/tests/test_copy_tone_metadata_contracts.py
- orchestrator/tests/test_copy_tone_policy.py
- orchestrator/tests/test_copy_visual_overlay_review_script.py
- orchestrator/tests/test_copy_visual_validation.py
"""


# ===== from test_copy_candidates_branch.py =====
import json

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node, state_update_selected_copy_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext
from orchestrator.tests.factories.copy_payloads import make_copy_selection_payload, make_selected_copy_report
from orchestrator.tests.helpers.copywriting import make_copy_state


def _state():
    return make_copy_state()


def _state_for_context(business_type: str, item_or_service: str, promotion_goal: str):
    return make_copy_state(
        business_type=business_type,
        item_or_service=item_or_service,
        promotion_goal=promotion_goal,
    )


def test_copy_candidate_generation_is_stable_and_safe():
    update = copy_candidate_generation_node(_state())
    candidates = update["copy_candidates"]
    rendered = " ".join(str(value) for candidate in candidates for value in candidate.values())

    assert [candidate["id"] for candidate in candidates] == ["copy_1", "copy_2"]
    assert "010-" not in rendered
    assert "주소" not in rendered
    assert "%" not in rendered
    json.dumps({"candidates": candidates}, ensure_ascii=False)


def test_copy_candidate_generation_does_not_leak_option_value_codes():
    state = _state()
    state["context"]["item_or_service"] = "reservation_service"

    update = copy_candidate_generation_node(state)
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "reservation_service" not in rendered
    assert "예약 서비스" in rendered
    assert "한 판" not in rendered
    assert "회식은 역시 예약 서비스" not in rendered


def test_copy_candidate_generation_uses_cafe_appropriate_fallback_copy():
    update = copy_candidate_generation_node(_state_for_context("cafe", "딸기라떼", "discount_event"))
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "딸기라떼" in rendered
    assert "혜택" in rendered
    assert "한 판" not in rendered
    assert "회식" not in rendered
    assert "예약 문의" not in rendered


def test_selected_copy_updates_marketing_copy_and_copy_spec():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    selected_candidate = next(candidate for candidate in state["copy_candidates"] if candidate["id"] == "copy_2")
    state["copy_selection"] = make_copy_selection_payload("copy_2")
    state.update(state_update_selected_copy_node(state))
    state.update(copy_spec_parser_node(state))

    assert state["selected_copy_id"] == "copy_2"
    assert state["marketing_copy"]["headline"] == selected_candidate["headline"]
    assert state["copy_spec"]["items"][0]["role"] == "headline"


def test_selected_copy_node_uses_persisted_state_selection_without_resume_payload():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    selected_candidate = next(candidate for candidate in state["copy_candidates"] if candidate["id"] == "copy_2")
    state["selected_copy_id"] = "copy_2"
    state["selected_channel_id"] = "instagram-story"
    state["selected_tone"] = "깔끔한"
    state["custom_direction"] = "상품을 더 크게 보여줘"

    update = state_update_selected_copy_node(state)

    assert update["selected_copy_id"] == "copy_2"
    assert update["selected_channel_id"] == "instagram-story"
    assert update["selected_ad_format"] == "instagram_story"
    assert update["selected_tone"] == "깔끔한"
    assert update["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["marketing_copy"]["headline"] == selected_candidate["headline"]


def test_selected_copy_persists_frontend_choices_in_graph_state():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = make_copy_selection_payload(
        "copy_1",
        selected_channel_id="instagram-story",
        selected_tone="깔끔한",
        custom_direction="상품을 더 크게 보여줘",
    )

    update = state_update_selected_copy_node(state)

    assert update["selected_channel_id"] == "instagram-story"
    assert update["selected_ad_format"] == "instagram_story"
    assert update["selected_tone"] == "깔끔한"
    assert update["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["context"]["brand_tone"] == "깔끔한"
    assert update["context"]["extra"]["ad_format"] == "instagram_story"
    assert update["context"]["extra"]["selected_channel_id"] == "instagram-story"
    assert update["current_brief"]["selected_channel_id"] == "instagram-story"
    assert update["current_brief"]["selected_tone"] == "깔끔한"
    assert update["current_brief"]["custom_direction"] == "상품을 더 크게 보여줘"
    assert update["ad_format_spec"]["ad_format"] == "instagram_story"
    assert update["ad_format_spec"]["height"] == 1920
    assert update["layout_spec"]["layout_type"] == "story_vertical"


def test_selected_copy_node_prefers_custom_copy_from_candidate_selection_resume():
    state = _state()
    state.update(copy_candidate_generation_node(state))
    state["copy_selection"] = make_copy_selection_payload(
        "copy_2",
        user_custom_headline="내가 고친 삼겹살 문구",
        user_custom_subcopy="오늘 저녁 예약 가능",
    )

    update = state_update_selected_copy_node(state)

    assert update["selected_copy_id"] == "copy_2"
    assert update["user_custom_headline"] == "내가 고친 삼겹살 문구"
    assert update["user_custom_subcopy"] == "오늘 저녁 예약 가능"
    assert update["marketing_copy"]["headline"] == "내가 고친 삼겹살 문구"
    assert update["marketing_copy"]["subcopy"] == "오늘 저녁 예약 가능"
    assert update["marketing_copy"]["metadata"]["copy_resolution"] == "manual_edit"


# ===== from test_copy_generation_mode_options.py =====
from orchestrator.app.llm.option_registry import OPTION_QUESTION_REGISTRY


def test_copy_generation_mode_option_question_exists_with_dependencies():
    question = OPTION_QUESTION_REGISTRY["copy_generation_mode"]
    values = {option.value for option in question.options}

    assert values == {"suggest_candidates", "auto_pilot", "no_copy", "custom_input"}
    dependency = question.metadata["dependency_fields"]
    assert dependency["if_value_equals"] == "custom_input"
    fields = {item["field"] for item in dependency["show_sub_fields"]}
    assert {"user_custom_headline", "user_custom_subcopy"} <= fields


def test_engine_and_copy_space_questions_are_not_reintroduced():
    assert "generation_engine" not in OPTION_QUESTION_REGISTRY
    assert "copy_space" not in OPTION_QUESTION_REGISTRY


# ===== from test_copy_generation_mode_schema.py =====
from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas import llm_marketing as schema


def test_copy_generation_mode_literal_and_initial_request_fields():
    assert set(get_args(schema.CopyGenerationMode)) == {"suggest_candidates", "auto_pilot", "no_copy", "custom_input"}

    request = schema.InitialMarketingRequest(user_input="ready", copy_generation_mode="no_copy")
    state = create_initial_marketing_state(request)

    assert state["copy_generation_mode"] == "no_copy"
    assert state["copy_required"] is False
    assert state["text_overlay_pending"] is False


def test_copy_mode_related_schema_models_validate():
    candidate = schema.CopyCandidate(id="copy_1", headline="오늘의 메뉴")
    output = schema.CopyCandidateListOutput(candidates=[candidate], recommended_candidate_id="copy_1")
    custom = schema.CustomCopyInput(headline="직접 쓴 문구")
    tone = schema.ToneBindingOutput(tone_profile="warm", forbidden_claims=["no phone"])
    inference = schema.CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=0.8, source="heuristic")

    assert output.generation_mode == "suggest_candidates"
    assert custom.headline == "직접 쓴 문구"
    assert tone.tone_profile == "warm"
    assert inference.confidence == 0.8
    with pytest.raises(ValidationError):
        schema.CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=1.5, source="heuristic")


# ===== from test_copy_grounding_visual_intent.py =====
import argparse

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.copy_fallbacks import build_message_strategy
from orchestrator.app.llm.copy_grounding import evaluate_copy_grounding
from orchestrator.app.llm.copy_prompts import build_copy_generation_v2_prompt
from orchestrator.app.llm.copy_quality_v2 import rank_copy_candidates
from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, InitialMarketingRequest, MarketingContext, MarketingCopy
from scripts import run_copy_quality_visual_actual as visual


def test_wrong_domain_smartphone_copy_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(
        id="copy_1",
        headline="당신의 소중한 순간을 스마트폰으로 더 빛나게",
        subcopy="감동과 편리함이 공존하는 스마트폰을 경험하세요",
        cta="체험해보기",
    )

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.grounded is False
    assert "스마트폰" in grounding.wrong_domain_terms
    assert ranking.scorecards[0].hard_blocked is True
    assert ranking.recommended_candidate_id is None


def test_grounded_macaron_copy_can_pass():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="다채로운 맛을 고르는 달콤한 시간", cta="라인업 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.grounded is True
    assert ranking.scorecards[0].hard_blocked is False
    assert ranking.recommended_candidate_id == "copy_1"


def test_domain_anchor_only_is_not_grounded():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="오늘의 달콤한 시간", subcopy="맛있는 디저트를 만나보세요", cta="")

    grounding = evaluate_copy_grounding(candidate, context=context)

    assert grounding.grounded is False
    assert grounding.grounding_level == "partial"
    assert "domain_anchor_only" in grounding.reasons


def test_single_weak_electronics_term_does_not_hard_block_product_anchor():
    context = MarketingContext(business_type="photo_studio", item_or_service="프로필 촬영", promotion_goal="reservation_cta")
    candidate = CopyCandidate(id="copy_1", headline="프로필 촬영", subcopy="카메라 앞 자연스러운 표정을 남겨요", cta="예약 문의")

    grounding = evaluate_copy_grounding(candidate, context=context)

    assert grounding.grounded is True
    assert grounding.wrong_domain_terms == []


def test_actual_prompt_contains_context_strategy_and_wrong_domain_examples():
    context = MarketingContext(business_type="restaurant_bbq", item_or_service="숯불구이", promotion_goal="reservation_cta")
    intent = resolve_copy_visual_intent(context)
    prompt = build_copy_generation_v2_prompt(context=context, strategy=build_message_strategy(context), visual_intent=intent)

    assert "숯불구이" in prompt
    assert "reservation_cta" not in prompt
    assert "스마트폰" in prompt


def test_a6_copy_prompt_does_not_describe_raw_bbq_value_as_grill_business():
    context = MarketingContext(
        business_type="restaurant_bbq",
        item_or_service="감자튀김",
        promotion_goal="brand_awareness",
    )
    strategy = build_message_strategy(context)
    intent = resolve_copy_visual_intent(context)
    prompt = build_copy_generation_v2_prompt(context=context, strategy=strategy, visual_intent=intent)

    assert "숯불구이 음식점" not in prompt
    assert "'business_category': 'local business'" in prompt


def test_a6_copy_prompt_does_not_describe_ambiguous_beauty_as_skincare():
    context = MarketingContext(
        business_type="beauty_salon",
        item_or_service="첫 방문 혜택",
        promotion_goal="brand_awareness",
    )
    strategy = build_message_strategy(context)
    intent = resolve_copy_visual_intent(context)
    prompt = build_copy_generation_v2_prompt(context=context, strategy=strategy, visual_intent=intent)

    assert "스킨케어" not in prompt
    assert "'business_category': 'local business'" in prompt


def test_router_knows_copy_generation_v2_actual(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_MODEL", "gpt-4.1-mini")
    selection = choose_model("copy_generation_v2_actual", "premium", latency_budget="standard")

    assert selection.selected_model_class in {"api_mini", "api_full"}
    assert selection.provider == "openai"
    assert selection.model_name in {"gpt-4.1-mini", "gpt-5.4-mini"}
    assert "unknown node" not in selection.reason


def test_copy_visual_intent_controls_cta_and_plate_policy():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery", brand_tone="premium")
    request = InitialMarketingRequest(user_input="macaron", user_plan="premium", context=context)
    state = create_initial_marketing_state(request)
    state["marketing_copy"] = MarketingCopy(headline="마카롱 컬렉션", subcopy="다채로운 맛", cta="").model_dump()
    state["copy_visual_intent"] = resolve_copy_visual_intent(context).model_dump()
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "width": 1024, "height": 1024}

    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))

    assert not any(item["role"] == "cta" for item in state["copy_spec"]["items"])
    assert not any(slot["role"] == "cta" for slot in state["text_layout_spec"]["slots"])
    assert state["text_style_spec"]["typography"]["use_text_plate"] is False


def test_copy_visual_intent_reference_hints_affect_style_and_layout():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery", brand_tone="premium")
    reference = {"layout_hint": "editorial left text right product", "typography_hint": "premium serif with restrained sans body"}
    request = InitialMarketingRequest(user_input="macaron", user_plan="premium", context=context)
    state = create_initial_marketing_state(request)
    state["selected_reference_template"] = reference
    state["marketing_copy"] = MarketingCopy(headline="마카롱 컬렉션", subcopy="오늘의 달콤한 선택", cta="").model_dump()
    state["copy_visual_intent"] = resolve_copy_visual_intent(context, selected_reference_template=reference).model_dump()
    state["ad_format_spec"] = {"ad_format": "instagram_feed", "width": 1024, "height": 1024}

    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))

    assert state["text_style_spec"]["typography"]["headline_font"] == "RIDIBatang"
    assert state["text_layout_spec"]["template"] == "left_text_right_product"
    assert {slot["alignment"] for slot in state["text_layout_spec"]["slots"]} == {"left"}


def test_vlm_hard_gate_prevents_wrong_domain_v2_preference():
    normalized = visual.normalize_vlm_payload(
        {
            "baseline_copy_score": 6,
            "v2_copy_score": 9,
            "baseline_natural_korean": 6,
            "v2_natural_korean": 9,
            "baseline_business_fit": 7,
            "v2_business_fit": 9,
            "baseline_specificity": 6,
            "v2_specificity": 9,
            "baseline_emotional_pull": 6,
            "v2_emotional_pull": 9,
            "baseline_cta_relevance": 6,
            "v2_cta_relevance": 9,
            "baseline_generic_phrase": False,
            "v2_generic_phrase": False,
            "baseline_unsupported_claim": False,
            "v2_unsupported_claim": False,
            "baseline_text_readable": True,
            "v2_text_readable": True,
            "copy_matches_product": False,
            "wrong_domain_terms": ["스마트폰"],
            "preferred_version": "v2",
        }
    )

    assert normalized["preferred_version"] != "v2"


def test_visual_runner_uses_production_copy_style_layout_nodes(monkeypatch, tmp_path):
    calls = {"copy": 0, "style": 0, "layout": 0}

    def wrap(name, fn):
        def inner(state):
            calls[name] += 1
            return fn(state)

        return inner

    monkeypatch.setattr(visual, "copy_spec_parser_node", wrap("copy", visual.copy_spec_parser_node))
    monkeypatch.setattr(visual, "text_style_binder_node", wrap("style", visual.text_style_binder_node))
    monkeypatch.setattr(visual, "text_layout_planner_node", wrap("layout", visual.text_layout_planner_node))

    from PIL import Image

    background = tmp_path / "bg.png"
    Image.new("RGB", (1024, 1024), "white").save(background)
    output = visual.render_baseline_and_v2_copy(
        "macaron_collection_001",
        background,
        {"headline": "마카롱 컬렉션", "subcopy": "다채로운 맛", "cta": ""},
        tmp_path / "out",
        "grounded",
    )

    assert output.exists()
    assert calls == {"copy": 1, "style": 1, "layout": 1}


def test_menu_discovery_strategy_does_not_create_consultation_intent():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    strategy = build_message_strategy(context)

    assert strategy.conversion_goal == "menu_discovery"
    assert strategy.cta_intent == "explore_menu"
    assert "상담" not in " ".join([strategy.customer_desire or "", strategy.proof_or_detail or "", strategy.cta_intent or ""])


def test_macaron_consultation_cta_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="다채로운 맛을 가볍게 골라보세요", cta="상담 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.grounded is False
    assert grounding.cta_goal_mismatch_terms
    assert grounding.product_drift_terms == []
    assert grounding.internal_terms == []
    assert ranking.scorecards[0].hard_blocked is True


def test_macaron_meat_product_drift_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="고기 메뉴처럼 든든한 식사 메뉴", cta="컬렉션 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.cta_goal_mismatch_terms == []
    assert grounding.product_drift_terms
    assert grounding.internal_terms == []
    assert ranking.scorecards[0].hard_blocked is True


def test_internal_enum_menu_discovery_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="menu_discovery 마카롱", subcopy="product_first 전략", cta="컬렉션 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.cta_goal_mismatch_terms == []
    assert grounding.product_drift_terms == []
    assert grounding.internal_terms
    assert ranking.scorecards[0].hard_blocked is True


def test_generic_strategy_words_are_not_product_anchors():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="상담 가능한 서비스", subcopy="필요한 구성을 선택하세요", cta="")

    grounding = evaluate_copy_grounding(candidate, context=context, strategy=build_message_strategy(context))

    assert grounding.grounded is False
    assert grounding.product_terms_found == []


# ===== from test_copy_llm_v1.py =====
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.node_runner import append_llm_call_result_safe
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_validation_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, InitialMarketingRequest, MarketingContext
from orchestrator.app.schemas.llm_model_policy import LLMCallResult, ModelSelection


def _state__test_copy_llm_v1(user_plan: str = "premium", mode: str = "suggest_candidates"):
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


def test_copy_candidates_free_plan_marks_rule_based_origin():
    update = copy_candidate_generation_node(_state__test_copy_llm_v1("free"))

    assert update["copy_candidates"]
    assert update["copy_candidate_origin"] == "rule_based"
    assert update["llm_call_results"][0]["error"] == "free_plan_deterministic_fallback"


def test_copy_candidates_disabled_uses_rule_based_fallback():
    update = copy_candidate_generation_node(_state__test_copy_llm_v1("premium"))

    assert update["copy_candidates"]
    assert update["copy_candidate_origin"] == "fallback"
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

    update = copy_candidate_generation_node(_state__test_copy_llm_v1("premium"))

    assert update["copy_candidate_origin"] == "llm"
    assert update["copy_candidates"][0]["id"] == "x"
    assert update["copy_candidates"][0]["headline"] == "딸기 케이크 신메뉴"
    assert update["copy_candidates"][0]["metadata"]["copy_tone_policy"]["policy_id"] == "cafe_v1"


def test_copy_candidate_hallucinated_phone_or_discount_falls_back(monkeypatch):
    unsafe = CopyCandidateListOutput(
        candidates=[CopyCandidate(id="x", headline="딸기 케이크 50% 할인", subcopy="010-1234-5678로 주문", cta="전화하기")],
        recommended_candidate_id="x",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.copy_candidates.run_structured_node", lambda *args, **kwargs: (unsafe, {"fallback_used": False}))

    update = copy_candidate_generation_node(_state__test_copy_llm_v1("premium"))
    rendered = " ".join(str(value) for candidate in update["copy_candidates"] for value in candidate.values())

    assert "010-1234-5678" not in rendered
    assert "50%" not in rendered
    assert update["copy_candidate_origin"] == "fallback"
    assert update["copywriting_output"]["metadata"]["llm_metadata"]["fallback_reason"] == "llm_candidate_validation_failed"


def test_custom_input_is_not_rewritten():
    state = _state__test_copy_llm_v1("premium", mode="custom_input")
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
    append_llm_call_result_safe(
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
    update = auto_pilot_copywriting_node(_state__test_copy_llm_v1("free", mode="auto_pilot"))

    assert update["marketing_copy"]["headline"]
    assert update["llm_call_results"][0]["error"] == "free_plan_deterministic_fallback"


# ===== from test_copy_mode_inference.py =====
from orchestrator.app.graph.nodes import infer_copy_generation_mode, validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_copy_mode_heuristics():
    assert infer_copy_generation_mode("카피 없이 이미지만") == "no_copy"
    assert infer_copy_generation_mode("문구는 내가 넣을게") == "custom_input"
    assert infer_copy_generation_mode("알아서 문구까지 만들어줘") == "auto_pilot"
    assert infer_copy_generation_mode("카피 여러 개 추천해줘") == "suggest_candidates"


def test_unknown_copy_mode_remains_missing():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(validator_node(state))

    assert "copy_generation_mode" in state["missing_fields"]


def test_initial_request_copy_mode_beats_heuristic():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="카피 없이 이미지만",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state.update(validator_node(state))

    assert state["copy_generation_mode"] == "auto_pilot"
    assert "copy_generation_mode" not in state["missing_fields"]


# ===== from test_copy_mode_router.py =====
from orchestrator.app.graph.routers import route_after_tone_binding


def test_copy_mode_router_branches():
    assert route_after_tone_binding({"copy_generation_mode": "suggest_candidates"}) == "copy_candidate_generation"
    assert route_after_tone_binding({"copy_generation_mode": "auto_pilot"}) == "auto_pilot_copywriting"
    assert route_after_tone_binding({"copy_generation_mode": "custom_input"}) == "custom_copy_input"
    assert route_after_tone_binding({"copy_generation_mode": "no_copy"}) == "no_copy_bypass"
    assert route_after_tone_binding({"copy_generation_mode": None}) == "auto_pilot_copywriting"


# ===== from test_copy_quality.py =====
from orchestrator.app.llm.copy_quality import apply_copy_quality_policy, normalize_cta, sanitize_copy_text, score_copy_quality, shorten_headline
from orchestrator.app.schemas.llm_marketing import MarketingCopy


def test_copy_quality_scores_without_destructive_rewrite():
    copy = MarketingCopy(headline="대박 신메뉴!! 지금 바로", subcopy="  최고의 혜택입니다!!  ", cta="지금 바로 확인하기")
    fixed = apply_copy_quality_policy(copy)

    assert "대박" in fixed.headline
    assert "!!" not in fixed.subcopy
    assert fixed.cta == "지금 바로 확인하기"
    assert fixed.metadata["copy_quality"]["score"] < 1
    assert fixed.metadata["copy_quality"]["applied_fixes"] == []


def test_copy_quality_helpers():
    assert sanitize_copy_text("오늘   좋아요!!") == "오늘 좋아요!"
    assert len(shorten_headline("놓치지 마세요 신메뉴 혜택 안내", max_chars=12)) <= 12
    assert normalize_cta("매장으로 자세히 문의하기") == "매장으로 자세히 문의하기"
    assert score_copy_quality({"headline": "대박 혜택!!"})["warnings"]


def test_sanitize_copy_text_strips_leaked_meta_labels():
    # Leaked internal label/format must be stripped, leaving only the visible copy.
    assert sanitize_copy_text("AI추천=신메뉴 치킨, 오늘의 기대감 / Sub: 이벤트 분위기로") == "신메뉴 치킨, 오늘의 기대감"
    assert sanitize_copy_text("Sub: 이벤트 분위기로 즐기는 저녁") == "이벤트 분위기로 즐기는 저녁"
    assert sanitize_copy_text("Headline: 봄을 닮은 한 잔") == "봄을 닮은 한 잔"
    # Normal copy must be left intact (no over-stripping).
    assert sanitize_copy_text("오늘 저녁, 따뜻한 치킨 한 판") == "오늘 저녁, 따뜻한 치킨 한 판"
    assert sanitize_copy_text("24/7 언제나 신선하게") == "24/7 언제나 신선하게"
    assert sanitize_copy_text("추천 메뉴, 딸기라떼") == "추천 메뉴, 딸기라떼"


# ===== from test_copy_quality_actual_batch_script.py =====
import json
import os
from pathlib import Path

import pytest

from scripts import _actual_env
from scripts import run_copy_quality_actual_batch as batch
from scripts import run_copy_quality_visual_actual as visual
from orchestrator.app.llm.copy_quality_v2 import build_deterministic_copy_output_v2
from orchestrator.app.t2i.engines.base import T2IGenerationOutput


ACTUAL_ENV_KEYS = [
    "OPENAI_API_KEY",
    "LLM_OPENAI_VISION_MODEL",
    "EASYADS_COPY_QUALITY_ACTUAL",
    "EASYADS_ENABLE_LLM_CALLS",
    "EASYADS_LLM_PROVIDER",
    "EASYADS_VLM_ACTUAL",
    "EASYADS_FLUX2_KLEIN_ACTUAL",
    "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL",
    "EASYADS_T2I_FLUX2_KLEIN_BACKEND",
    "EASYADS_T2I_FLUX2_KLEIN_DEVICE",
]


def clear_actual_env(monkeypatch):
    for key in ACTUAL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def clear_actual_env_direct():
    for key in ACTUAL_ENV_KEYS:
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def isolate_actual_env():
    clear_actual_env_direct()
    yield
    clear_actual_env_direct()


def test_env_file_loader_loads_docs_api_key_without_printing_secret(monkeypatch, tmp_path, capsys):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "# comment\nexport OPENAI_API_KEY='sk-secret-loader-test'\nLLM_OPENAI_VISION_MODEL=\"gpt-test\"\n",
        encoding="utf-8",
    )

    report = _actual_env.load_env_file(env_file)
    captured = capsys.readouterr()

    assert report["env_file_found"] is True
    assert "OPENAI_API_KEY" in report["loaded_keys"]
    assert "sk-secret-loader-test" not in captured.out
    assert "sk-secret-loader-test" not in json.dumps(report)
    assert Path(report["env_file"]).name == "api_key.env"
    assert visual.os.getenv("OPENAI_API_KEY") == "sk-secret-loader-test"


def test_copy_quality_actual_batch_dry_run_does_not_require_openai(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = type("Args", (), {"actual": False, "max_cases": 2, "max_openai_calls": 2, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "dry_run"
    assert report["total_cases"] == 2
    assert all(run["actual_openai_call"] is False for run in report["runs"])


def test_copy_quality_actual_batch_supports_explicit_cases(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = type(
        "Args",
        (),
        {
            "actual": False,
            "cases": ["macaron_collection_001", "car_detailing_001"],
            "max_cases": 6,
            "max_openai_calls": 2,
            "mode": "post",
            "env_file": None,
        },
    )()

    report = batch.build_report(args)

    assert [run["case_id"] for run in report["runs"]] == ["macaron_collection_001", "car_detailing_001"]
    assert all("selected_grounding" in run for run in report["runs"])


def test_copy_quality_actual_batch_blocks_without_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "OPENAI_API_KEY" in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]


def test_copy_quality_visual_actual_blocks_without_model_or_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_COPY_QUALITY_ACTUAL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", raising=False)
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": None})()

    report = visual.build_report(args)

    assert report["status"] == "blocked"
    assert report["runs"][0]["quality"] is None
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" in report["runs"][0]["missing_requirements"]
    assert "HF_TOKEN_or_HUGGINGFACE_TOKEN" not in report["runs"][0]["missing_requirements"]


def test_copy_quality_actual_batch_calls_actual_runner_when_guarded(monkeypatch):
    calls = []

    def fake_run_actual_copy_generation(state):
        calls.append(state["context"]["business_type"])
        output = build_deterministic_copy_output_v2(state)
        return output, {"llm_attempted": True, "fallback_used": False, "model_name": "gpt-test", "llm_call_result": {"token_usage": {"input_tokens": 3, "output_tokens": 4}}}

    monkeypatch.setattr(batch, "run_actual_copy_generation", fake_run_actual_copy_generation)
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 1, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert calls == ["macaron"]
    assert report["status"] == "completed"
    assert report["call_budget"]["attempted"] == 1
    assert report["call_budget"]["succeeded"] == 1
    assert report["runs"][0]["actual_openai_call"] is True
    assert report["runs"][0]["selected_copy"]
    assert len(report["runs"][0]["candidates"]) == 3
    assert report["runs"][0]["model_name"] == "gpt-test"


def test_copy_quality_actual_batch_enforces_call_budget(monkeypatch):
    monkeypatch.setenv("EASYADS_COPY_QUALITY_ACTUAL", "1")
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 0, "mode": "post", "env_file": None})()

    report = batch.build_report(args)

    assert report["status"] == "blocked"
    assert "max_openai_calls_positive" in report["runs"][0]["missing_requirements"]


def test_text_actual_uses_env_file_before_missing_check(monkeypatch, tmp_path):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "OPENAI_API_KEY=sk-from-file\nEASYADS_COPY_QUALITY_ACTUAL=1\nEASYADS_ENABLE_LLM_CALLS=true\nEASYADS_LLM_PROVIDER=openai\n",
        encoding="utf-8",
    )
    args = type("Args", (), {"actual": True, "max_cases": 1, "max_openai_calls": 0, "mode": "post", "env_file": str(env_file)})()

    report = batch.build_report(args)

    assert "OPENAI_API_KEY" not in report["runs"][0]["missing_requirements"]
    assert "EASYADS_COPY_QUALITY_ACTUAL=1" not in report["runs"][0]["missing_requirements"]


def test_visual_actual_uses_env_file_before_missing_check(monkeypatch, tmp_path):
    clear_actual_env(monkeypatch)
    env_file = tmp_path / "api_key.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-file",
                "EASYADS_COPY_QUALITY_ACTUAL=1",
                "EASYADS_VLM_ACTUAL=1",
                "EASYADS_FLUX2_KLEIN_ACTUAL=1",
                "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true",
                "EASYADS_T2I_FLUX2_KLEIN_BACKEND=local_diffusers",
                "EASYADS_T2I_FLUX2_KLEIN_DEVICE=cuda",
            ]
        ),
        encoding="utf-8",
    )
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": str(env_file)})()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert "OPENAI_API_KEY" not in report["missing_requirements"]
    assert report["runs"][0]["error_code"] == "ValueError"


def test_visual_actual_fails_without_copy_report_in_actual_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(visual, "missing_actual_requirements", lambda args: [])
    args = type("Args", (), {"actual": True, "cases": ["macaron_collection_001"], "max_images": 1, "copy_report": None, "env_file": None})()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert report["runs"][0]["error_code"] == "ValueError"


def test_visual_actual_success_path_uses_flux_renderer_and_vlm(monkeypatch, tmp_path):
    calls = {"flux": 0, "render": 0, "vlm": 0}
    background = tmp_path / "background.png"

    def fake_flux(case_id, *, case_dir, seed):
        calls["flux"] += 1
        from PIL import Image

        Image.new("RGB", (128, 128), (40, 40, 40)).save(background)
        return T2IGenerationOutput(
            engine="flux2_klein_4b",
            image_paths=[str(background)],
            latency_ms=12,
            metadata={"provider": "local_diffusers", "execution_backend": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B"},
        )

    def fake_render(case_id, background_path, copy, output_dir, label):
        calls["render"] += 1
        from PIL import Image

        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{label}.png"
        Image.new("RGB", (128, 128), (80 if label == "baseline" else 120, 80, 80)).save(path)
        return path

    def fake_vlm(case_id, baseline_path, v2_path):
        calls["vlm"] += 1
        return visual.CopyActualComparisonResult(
            baseline_copy_score=5,
            v2_copy_score=8,
            baseline_natural_korean=5,
            v2_natural_korean=8,
            baseline_business_fit=5,
            v2_business_fit=8,
            baseline_specificity=4,
            v2_specificity=7,
            baseline_emotional_pull=4,
            v2_emotional_pull=7,
            baseline_cta_relevance=5,
            v2_cta_relevance=8,
            baseline_generic_phrase=True,
            v2_generic_phrase=False,
            baseline_unsupported_claim=False,
            v2_unsupported_claim=False,
            baseline_text_readable=True,
            v2_text_readable=True,
            preferred_version="v2",
            improvement_reasons=["more specific"],
        )

    monkeypatch.setattr(visual, "generate_flux2_background", fake_flux)
    monkeypatch.setattr(visual, "render_baseline_and_v2_copy", fake_render)
    monkeypatch.setattr(visual, "run_actual_vlm_comparison", fake_vlm)

    run = visual.run_actual_copy_case(
        "macaron_collection_001",
        case_dir=tmp_path / "case",
        seed=42,
        copy_report=make_selected_copy_report(),
        max_vlm_calls=1,
    )

    assert run["status"] == "completed"
    assert calls == {"flux": 1, "render": 3, "vlm": 1}
    assert run["previous_baseline_path"]
    assert run["previous_v2_path"]
    assert run["grounded_intent_v1_path"]


def test_vlm_actual_comparison_success_path(monkeypatch, tmp_path):
    from PIL import Image

    baseline = tmp_path / "baseline.png"
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (16, 16), "white").save(baseline)
    Image.new("RGB", (16, 16), "black").save(v2)

    payload = {
        "baseline_copy_score": 5,
        "v2_copy_score": 8,
        "baseline_natural_korean": 5,
        "v2_natural_korean": 8,
        "baseline_business_fit": 5,
        "v2_business_fit": 8,
        "baseline_specificity": 5,
        "v2_specificity": 8,
        "baseline_emotional_pull": 5,
        "v2_emotional_pull": 8,
        "baseline_cta_relevance": 5,
        "v2_cta_relevance": 8,
        "baseline_generic_phrase": True,
        "v2_generic_phrase": False,
        "baseline_unsupported_claim": False,
        "v2_unsupported_claim": False,
        "baseline_text_readable": True,
        "v2_text_readable": True,
        "preferred_version": "v2",
        "improvement_reasons": ["more specific"],
        "remaining_copy_issues": [],
        "layout_issues": [],
    }

    class FakeResponse:
        output_text = json.dumps(payload)

    def fake_create(**kwargs):
        assert kwargs["model"]
        assert all(str(path).endswith(".png") for path in kwargs["image_paths"])
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-redacted")
    monkeypatch.setattr(visual, "_create_openai_vision_response", fake_create)

    result = visual.run_actual_vlm_comparison("macaron_collection_001", baseline, v2, v2)

    assert result.preferred_version == "v2"
    assert result.v2_copy_score == 8


def test_vlm_not_implemented_never_completed(monkeypatch, tmp_path):
    from PIL import Image

    background = tmp_path / "background.png"

    def fake_flux(case_id, *, case_dir, seed):
        Image.new("RGB", (128, 128), (40, 40, 40)).save(background)
        return T2IGenerationOutput(
            engine="flux2_klein_4b",
            image_paths=[str(background)],
            latency_ms=12,
            metadata={"provider": "local_diffusers", "execution_backend": "local_diffusers", "model_name": "black-forest-labs/FLUX.2-klein-4B"},
        )

    def fake_render(case_id, background_path, copy, output_dir, label):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{label}.png"
        Image.new("RGB", (128, 128), (80 if label == "baseline" else 120, 80, 80)).save(path)
        return path

    copy_report = tmp_path / "post_actual.json"
    copy_report.write_text(
        json.dumps({"runs": [{"case_id": "macaron_collection_001", "selected_copy": {"headline": "마카롱 컬렉션", "subcopy": "달콤한 색을 고르는 시간", "cta": "라인업 보기"}}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(visual, "missing_actual_requirements", lambda args: [])
    monkeypatch.setattr(visual, "generate_flux2_background", fake_flux)
    monkeypatch.setattr(visual, "render_baseline_and_v2_copy", fake_render)
    monkeypatch.setattr(visual, "run_actual_vlm_comparison", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vlm_not_available")))
    args = type(
        "Args",
        (),
        {
            "actual": True,
            "cases": ["macaron_collection_001"],
            "max_images": 1,
            "copy_report": str(copy_report),
            "output_dir": str(tmp_path / "visual"),
            "seeds": [42],
            "max_vlm_calls": 1,
            "env_file": None,
        },
    )()

    report = visual.build_report(args)

    assert report["status"] == "failed"
    assert report["runs"][0]["status"] == "failed"
    assert report["runs"][0]["error_code"] == "RuntimeError"


def test_visual_false_positive_rejects_mock_flux_result(tmp_path):
    image = tmp_path / "mock.png"
    image.write_bytes(b"not an image")
    result = T2IGenerationOutput(engine="mock", image_paths=[str(image)], latency_ms=1, metadata={"provider": "mock"})

    try:
        visual.assert_actual_flux_result(result)
    except AssertionError as exc:
        assert "flux2_klein_4b" in str(exc)
    else:
        raise AssertionError("mock result should not pass actual FLUX validation")


# ===== from test_copy_quality_v2.py =====
from orchestrator.app.llm.copy_fallbacks import THEMES, generate_fallback_candidates, resolve_copy_theme
from orchestrator.app.llm.copy_quality_v2 import (
    build_deterministic_copy_output_v2,
    contains_generic_meta_phrase,
    rank_copy_candidates,
    select_recommended_copy,
    validate_candidate_diversity,
)
from orchestrator.app.schemas.llm_marketing import CopyCandidate, MarketingContext


def test_copy_fallbacks_cover_at_least_ten_themes():
    assert len(THEMES) >= 10


BBQ_BIASED_COPY_TERMS = ("숯불", "불판", "회식", "구워", "구이", "한상")


@pytest.mark.parametrize("business_type", ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"])
def test_a6_restaurant_and_bbq_like_fallback_theme_is_neutral(business_type):
    theme = resolve_copy_theme(business_type)

    assert theme.key == "generic"


@pytest.mark.parametrize("business_type", ["restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"])
def test_a6_restaurant_and_bbq_like_fallback_copy_avoids_bbq_language(business_type):
    candidates = generate_fallback_candidates(
        MarketingContext(
            business_type=business_type,
            item_or_service="감자튀김",
            promotion_goal="brand_awareness",
        )
    )
    joined = " ".join(
        " ".join(filter(None, [candidate.headline, candidate.subcopy, candidate.cta]))
        for candidate in candidates
    )

    assert all(term not in joined for term in BBQ_BIASED_COPY_TERMS)


@pytest.mark.parametrize("business_type", ["beauty", "beauty_salon", "salon"])
def test_a6_ambiguous_beauty_fallback_theme_is_neutral(business_type):
    theme = resolve_copy_theme(business_type)

    assert theme.key == "generic"


@pytest.mark.parametrize(
    ("business_type", "expected_theme"),
    [
        ("beauty_skincare", "beauty_skincare"),
        ("skincare", "beauty_skincare"),
        ("beauty_hair", "beauty_hair"),
        ("hair", "beauty_hair"),
        ("beauty_nail", "beauty_nail"),
        ("nail", "beauty_nail"),
        ("beauty_spa", "beauty_spa"),
        ("spa", "beauty_spa"),
    ],
)
def test_a6_exact_beauty_subtype_fallback_theme_stays_specialized(business_type, expected_theme):
    theme = resolve_copy_theme(business_type)

    assert theme.key == expected_theme


def test_fallback_candidates_use_three_distinct_angles():
    candidates = generate_fallback_candidates(MarketingContext(business_type="cafe", item_or_service="딸기라떼"))

    assert [candidate.angle for candidate in candidates] == ["product_first", "emotion_first", "benefit_action_first"]
    assert validate_candidate_diversity(candidates)["overall_pass"] is True


def test_ranker_hard_blocks_generic_meta_phrase():
    candidates = [
        CopyCandidate(id="copy_1", headline="상품의 장점을 쉽게 확인해보세요", cta="자세히 보기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="딸기라떼 신메뉴", subcopy="부드럽고 산뜻한 오늘의 한 잔", cta="신메뉴 보기", angle="emotion_first"),
    ]

    ranking = rank_copy_candidates(candidates, business_type="cafe")

    assert contains_generic_meta_phrase(candidates[0].headline)
    assert ranking.recommended_candidate_id == "copy_2"
    assert ranking.blocked_candidate_ids == ["copy_1"]


def test_ranker_flags_near_duplicate_candidates():
    candidates = [
        CopyCandidate(id="copy_1", headline="딸기라떼 신메뉴", subcopy="오늘의 달콤한 한 잔", cta="메뉴 보기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="딸기라떼 신메뉴", subcopy="오늘의 달콤한 한 잔", cta="메뉴 보기", angle="product_first"),
        CopyCandidate(id="copy_3", headline="오늘의 달콤한 한 잔", subcopy="부드러운 카페 메뉴", cta="신메뉴 보기", angle="emotion_first"),
    ]

    diversity = validate_candidate_diversity(candidates)
    ranking = rank_copy_candidates(candidates, business_type="cafe")

    assert diversity["overall_pass"] is False
    assert ranking.diversity_warnings


def test_all_blocked_candidates_require_regeneration_without_recommendation():
    candidates = [
        CopyCandidate(id="copy_1", headline="상품의 장점을 쉽게 확인해보세요", cta="지금 확인하기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="필요한 정보를 간결하게 안내", cta="자세히 보기", angle="emotion_first"),
    ]

    ranking = rank_copy_candidates(candidates, business_type="generic")

    assert ranking.recommended_candidate_id is None
    assert ranking.requires_regeneration is True
    assert select_recommended_copy(candidates, ranking) is None


def test_copy_quality_v2_limits_candidates_to_three():
    output = build_deterministic_copy_output_v2({"context": MarketingContext(business_type="retail", item_or_service="컬렉션")}, max_candidates=5)

    assert len(output.candidates) == 3


def test_fallback_matrix_has_no_generic_meta_phrases_for_core_cases():
    contexts = [
        MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery"),
        MarketingContext(business_type="restaurant_bbq", item_or_service="숯불구이", promotion_goal="reservation_cta"),
        MarketingContext(business_type="beauty_nail", item_or_service="네일 디자인", promotion_goal="consultation"),
        MarketingContext(business_type="photo_studio", item_or_service="꽃다발 프로필 촬영", promotion_goal="reservation_cta"),
        MarketingContext(business_type="car_detailing", item_or_service="차량 디테일링", promotion_goal="inquiry"),
    ]

    for context in contexts:
        output = build_deterministic_copy_output_v2({"context": context})
        assert output.recommended_candidate_id
        assert all(not contains_generic_meta_phrase(" ".join([candidate.headline, candidate.subcopy or "", candidate.cta or ""])) for candidate in output.candidates)


def test_all_overlength_candidates_require_regeneration():
    long_text = "마카롱 컬렉션을 너무 길고 장황하게 설명하는 헤드라인입니다"
    candidates = [
        CopyCandidate(id="copy_1", headline=long_text, subcopy="다채로운 맛과 색을 아주 길게 계속 설명하는 문장입니다 문장입니다", cta="컬렉션 보기", angle="product_first"),
        CopyCandidate(id="copy_2", headline=long_text, subcopy="다채로운 맛과 색을 아주 길게 계속 설명하는 문장입니다 문장입니다", cta="컬렉션 보기", angle="emotion_first"),
        CopyCandidate(id="copy_3", headline=long_text, subcopy="다채로운 맛과 색을 아주 길게 계속 설명하는 문장입니다 문장입니다", cta="컬렉션 보기", angle="benefit_action_first"),
    ]

    ranking = rank_copy_candidates(candidates, state={"context": MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery").model_dump()})

    assert ranking.recommended_candidate_id is None
    assert ranking.requires_regeneration is True
    assert all(card.hard_blocked for card in ranking.scorecards)


def test_business_fit_cannot_be_perfect_with_product_drift():
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="고기와 식사 메뉴처럼 든든하게", cta="컬렉션 보기", angle="product_first")

    ranking = rank_copy_candidates([candidate], state={"context": MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery").model_dump()})

    assert ranking.scorecards[0].business_fit_score < 1.0
    assert ranking.scorecards[0].hard_blocked is True


def test_valid_short_macaron_editorial_copy_passes():
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="다채로운 맛과 색으로 고르는 오늘의 디저트", cta="컬렉션 보기", angle="product_first")

    ranking = rank_copy_candidates([candidate], state={"context": MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery").model_dump()})

    assert ranking.recommended_candidate_id == "copy_1"
    assert ranking.scorecards[0].hard_blocked is False


# ===== from test_copy_spec_parser_node.py =====
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def test_copy_spec_parser_maps_marketing_copy_roles_without_new_claims():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            context=MarketingContext(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta", extra={"ad_format": "instagram_feed"}),
        )
    )
    state["marketing_copy"] = {
        "headline": "오늘 회식은 삼겹살로 결정",
        "subcopy": "두툼하게 준비한 삼겹살과 편안한 자리",
        "cta": "예약 문의하기",
        "hashtags": ["#삼겹살"],
        "metadata": {},
    }

    update = copy_spec_parser_node(state)
    items = update["copy_spec"]["items"]
    rendered = " ".join(item["text"] for item in items)

    assert [item["role"] for item in items] == ["headline", "subheadline", "cta"]
    assert "010-" not in rendered
    assert "주소" not in rendered
    assert "%" not in rendered


# ===== from test_copy_tone.py =====
from orchestrator.app.llm.copy_tone import COPY_TONE_MAPPING, get_copy_tone_profile


def test_copy_tone_mapping_supports_required_business_types():
    assert set(COPY_TONE_MAPPING) == {
        "restaurant",
        "cafe",
        "beauty_salon",
        "bar",
        "fitness",
        "academy",
        "flower_shop",
        "store",
    }


def test_copy_tone_profile_returns_fallback_for_unknown_business_type():
    profile = get_copy_tone_profile("unknown_type", "unknown_persona")

    assert profile["voice"] == "friendly_clear"
    assert profile["business_type"] == "unknown_type"
    assert profile["target_persona"] == "unknown_persona"
    assert isinstance(profile["keywords"], list)


def test_copy_tone_profile_adds_persona_hint_when_known():
    profile = get_copy_tone_profile("restaurant", "office_worker")

    assert profile["voice"] == "friendly_clear"
    assert profile["business_type"] == "generic"
    assert profile["raw_business_type"] == "restaurant"
    assert profile["persona_hint"]["energy"] == "efficient"


# ===== from test_copy_tone_metadata_contracts.py =====
import json

from orchestrator.app.graph.nodes import build_copy_mode_prompt
from orchestrator.app.graph.nodes import resolve_copy_generation_mode
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.metadata_builders import (
    build_copy_generation_metadata,
    build_copy_mode_inference_metadata,
    build_copy_spec_parser_metadata,
    build_custom_copy_validation_metadata,
)
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.auto_pilot_copywriting import build_auto_pilot_prompt
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.copy_candidates import build_candidate_prompt
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_validation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.tone_binding import build_tone_binding_prompt
from orchestrator.app.llm.nodes.tone_binding import tone_binding_node
from orchestrator.app.schemas.llm_marketing import CopyCandidateListOutput, CopywritingOutput, InitialMarketingRequest, MarketingContext, MarketingCopy, ToneBindingOutput


def test_tone_binding_metadata_contains_context_format_and_layout():
    state = _state__test_copy_tone_metadata_contracts("auto_pilot")

    update = tone_binding_node(state)

    metadata = _llm_result_metadata(update["tone_binding_output"]["metadata"]["llm_metadata"])
    assert metadata["available_state"]["context"]["business_type"] == "restaurant"
    assert metadata["available_state"]["ad_format_spec"]["ad_format"] == "instagram_feed"
    assert metadata["available_state"]["layout_spec"]["layout_type"]


def test_copy_mode_inference_uses_metadata_contract_for_ambiguous_text():
    state = _state__test_copy_tone_metadata_contracts(None)

    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    metadata = state["llm_call_results"][0]["metadata"]
    assert mode is None
    assert output is None
    assert metadata["trace"]["node_name"] == "copy_mode_inference"
    assert metadata["available_state"]["latest_user_input"] == "ambiguous request"
    assert metadata["constraints"]["classify_only"] is True


def test_copy_candidate_metadata_contains_tone_policy():
    state = _state__test_copy_tone_metadata_contracts("suggest_candidates")

    update = copy_candidate_generation_node(state)

    metadata = _llm_result_metadata(update["copywriting_output"]["metadata"]["llm_metadata"])
    assert metadata["available_state"]["tone_binding_output"]["tone_profile"] == "warm"
    assert metadata["available_state"]["plan_policy"]["max_candidates"] == 2
    assert metadata["constraints"]["forbidden_claims"] == ["no fake discount"]
    assert metadata["constraints"]["channel_copy_rules"] == ["short CTA"]
    assert metadata["constraints"]["copy_constraints"] == ["no invented phone"]


def test_auto_pilot_metadata_contains_forbidden_claims():
    state = _state__test_copy_tone_metadata_contracts("auto_pilot")

    update = auto_pilot_copywriting_node(state)

    metadata = _llm_result_metadata(update["copywriting_output"]["metadata"]["llm_metadata"])
    assert metadata["trace"]["node_name"] == "auto_pilot_copywriting"
    assert metadata["available_state"]["tone_binding_output"]["forbidden_claims"] == ["no fake discount"]
    assert metadata["constraints"]["forbidden_claims"] == ["no fake discount"]


def test_custom_copy_validation_metadata_preserves_user_text():
    state = _state__test_copy_tone_metadata_contracts("custom_input")
    state["user_custom_headline"] = "Original headline"
    state["user_custom_subcopy"] = "Original subcopy"

    update = custom_copy_validation_node(state)

    full_metadata = build_custom_copy_validation_metadata(state)
    metadata = update["marketing_copy"]["metadata"]["llm_metadata_summary"]
    assert update["marketing_copy"]["headline"] == "Original headline"
    assert update["marketing_copy"]["subcopy"] == "Original subcopy"
    assert update["marketing_copy"]["metadata"]["preserved_user_copy"] is True
    assert full_metadata["available_state"]["user_custom_headline"] == "Original headline"
    assert "available_state" not in metadata
    assert metadata["constraints"]["preserve_user_copy"] is True
    assert metadata["constraints"]["no_rewrite"] is True


def test_copy_spec_parser_metadata_is_role_mapping_only():
    state = _state__test_copy_tone_metadata_contracts("auto_pilot")
    state["marketing_copy"] = MarketingCopy(headline="Original headline", subcopy="Original subcopy", cta="Book now").model_dump()

    update = copy_spec_parser_node(state)

    full_metadata = build_copy_spec_parser_metadata(state)
    metadata = update["copy_spec"]["metadata"]["llm_metadata_summary"]
    assert [item["role"] for item in update["copy_spec"]["items"]] == ["headline", "subheadline", "cta"]
    assert full_metadata["available_state"]["marketing_copy"]["headline"] == "Original headline"
    assert "available_state" not in metadata
    assert metadata["constraints"]["no_new_facts"] is True


def test_prompt_metadata_contracts_are_json_parseable():
    state = _state__test_copy_tone_metadata_contracts("auto_pilot")
    prompt_cases = [
        (build_tone_binding_prompt(state), "tone_binding"),
        (
            build_copy_mode_prompt("ambiguous request", state, build_copy_mode_inference_metadata(state, "ambiguous request")),
            "copy_mode_inference",
        ),
        (
            build_candidate_prompt(
                state,
                build_copy_generation_metadata(state, node_name="copy_candidate_generation", output_schema=CopyCandidateListOutput),
            ),
            "copy_candidate_generation",
        ),
        (
            build_auto_pilot_prompt(
                state,
                build_copy_generation_metadata(state, node_name="auto_pilot_copywriting", output_schema=CopywritingOutput),
            ),
            "auto_pilot_copywriting",
        ),
    ]

    for prompt, expected_node in prompt_cases:
        metadata = _metadata_contract_from_prompt(prompt)
        assert metadata["trace"]["node_name"] == expected_node
        assert metadata["output_rules"]["no_chain_of_thought"] is True


def _state__test_copy_tone_metadata_contracts(copy_generation_mode: str | None):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode=copy_generation_mode,
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="BBQ",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    state["tone_binding_output"] = ToneBindingOutput(
        tone_profile="warm",
        copy_constraints=["no invented phone"],
        recommended_copy_mode=copy_generation_mode or "auto_pilot",
        forbidden_claims=["no fake discount"],
        channel_copy_rules=["short CTA"],
        typography_hint="friendly",
    ).model_dump()
    return state


def _llm_result_metadata(llm_metadata: dict):
    return llm_metadata["llm_call_result"]["metadata"]


def _metadata_contract_from_prompt(prompt: str) -> dict:
    marker = "metadata_contract="
    start = prompt.index(marker) + len(marker)
    metadata, _ = json.JSONDecoder().raw_decode(prompt[start:].strip())
    return metadata


# ===== from test_copy_tone_policy.py =====
from orchestrator.app.llm.copy_tone_policy import (
    get_copy_tone_policy,
    normalize_copy_for_business,
)


def test_cafe_policy_warns_tacky_discount_terms_without_rewriting():
    result = normalize_copy_for_business(
        {"headline": "\uc5ed\ub300\uae09 \ub300\ubc15 \ub525\uae30\ub77c\ub5bc \uc2e0\uba54\ub274!!", "subcopy": "\ubbf8\uce5c \ud560\uc778", "cta": "\uc9c0\uae08 \ub9cc\ub098\ubcf4\uae30"},
        "cafe",
    )

    normalized = result["normalized_copy"]
    assert "\uc5ed\ub300\uae09" in normalized["headline"]
    assert "\ub300\ubc15" in normalized["headline"]
    assert "\ubbf8\uce5c \ud560\uc778" in normalized["subcopy"]
    assert "avoid_term_detected" in result["warnings"]


def test_a6_deprecated_bbq_policy_is_inventory_only_for_now():
    from orchestrator.app.llm.copy_tone_policy import POLICIES, resolve_copy_route_key

    deprecated_policy = POLICIES["restaurant_bbq"]

    assert deprecated_policy["policy_id"] == "restaurant_bbq_v1"
    assert deprecated_policy["promotion_style"] == "reservation_visit"
    assert resolve_copy_route_key("restaurant_bbq") == "generic"
    assert get_copy_tone_policy("restaurant_bbq")["policy_id"] == "generic_v1"


def test_beauty_skincare_policy_warns_medical_claims_without_rewriting():
    result = normalize_copy_for_business(
        {"headline": "100% \uac1c\uc120 \uae30\uc801 \ucf00\uc5b4", "subcopy": "\uc989\uc2dc \ud6a8\uacfc", "cta": "\uc0c1\ub2f4 \uc608\uc57d\ud558\uae30"},
        "beauty_skincare",
    )

    normalized = result["normalized_copy"]
    assert "100% \uac1c\uc120" in normalized["headline"]
    assert "\uae30\uc801" in normalized["headline"]
    assert "\uc989\uc2dc \ud6a8\uacfc" in normalized["subcopy"]
    assert "avoid_term_detected" in result["warnings"]


def test_beauty_hair_policy_has_hair_or_style_cta():
    policy = get_copy_tone_policy("beauty_hair")

    assert any("\uc2a4\ud0c0\uc77c" in candidate or "\ud5e4\uc5b4" in candidate for candidate in policy["cta_candidates"])


def test_custom_input_mode_does_not_rewrite_copy():
    copy = {"headline": "\uc5ed\ub300\uae09 \ub300\ubc15!!", "subcopy": "\uc6d0\ubb38 \uc720\uc9c0", "cta": "\ubb34\uc870\uac74 \ud074\ub9ad", "mode": "custom_input"}

    result = normalize_copy_for_business(copy, "cafe")

    assert result["normalized_copy"]["headline"] == "\uc5ed\ub300\uae09 \ub300\ubc15!!"
    assert result["normalized_copy"]["cta"] == "\ubb34\uc870\uac74 \ud074\ub9ad"
    assert "custom_input_not_rewritten" in result["warnings"]


def test_generated_mode_normalizes_excessive_punctuation():
    result = normalize_copy_for_business({"headline": "\uc2e0\uba54\ub274!!!", "subcopy": "\uc624\ub298\ub9cc!!!", "cta": "\ubcf4\uae30!!!"}, "generic")

    joined = " ".join(result["normalized_copy"].values())
    assert "!!" not in joined
    assert "normalized_spacing_or_punctuation" in result["applied_rules"]


# ===== from test_copy_visual_overlay_review_script.py =====
import json
from pathlib import Path

from PIL import Image

from scripts.run_copy_visual_overlay_review import run_overlay_review


def _write_report(path: Path, final_image_path: str | None = None):
    path.write_text(
        json.dumps(
            {
                "schema_version": "gpt_image2_quality_batch_report_v1",
                "cases": [
                    {
                        "case_id": "cafe_dessert_001",
                        "job_id": "job_test",
                        "business_type": "cafe",
                        "final_image_path": final_image_path,
                        "prompt_summary": {"business_type": "cafe"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_dry_run_does_not_require_real_outputs(tmp_path):
    report_path = tmp_path / "batch.json"
    _write_report(report_path, "missing/final_0.png")

    result = run_overlay_review(report=report_path, output_dir=tmp_path, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["cases"][0]["preview_image_path"] is None
    assert Path(result["report_json_path"]).exists()
    assert Path(result["report_md_path"]).exists()


def test_missing_report_returns_blocked_report(tmp_path):
    result = run_overlay_review(report=tmp_path / "missing.json", output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert "No GPT-image-2 quality batch report was found." in result["notes"]
    assert Path(result["report_json_path"]).exists()


def test_existing_temp_image_creates_preview(tmp_path):
    output_root = tmp_path / "outputs" / "job_test"
    output_root.mkdir(parents=True)
    image_path = output_root / "final_0.png"
    Image.new("RGB", (256, 256), (230, 210, 195)).save(image_path)
    report_path = tmp_path / "batch.json"
    _write_report(report_path, str(image_path))

    result = run_overlay_review(report=report_path, output_dir=tmp_path, max_cases=1)

    preview = Path(result["cases"][0]["preview_image_path"])
    assert result["cases"][0]["status"] == "preview_created"
    assert preview.exists()
    assert preview.name == "copy_visual_preview_0.png"


def test_report_does_not_include_raw_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    report_path = tmp_path / "batch.json"
    _write_report(report_path, "missing/final_0.png")

    result = run_overlay_review(report=report_path, output_dir=tmp_path, dry_run=True)

    report_text = Path(result["report_json_path"]).read_text(encoding="utf-8")
    assert "sk-secret-value" not in report_text


# ===== from test_copy_visual_validation.py =====
from pathlib import Path

from PIL import Image

from orchestrator.app.rendering.copy_visual_validation import (
    build_copy_visual_validation_report,
    estimate_text_contrast,
    validate_text_clipping,
    validate_text_safe_area,
)


def _save_image(path: Path, color: tuple[int, int, int]):
    Image.new("RGB", (120, 120), color).save(path)


def test_dark_background_recommends_light_text(tmp_path):
    image_path = tmp_path / "dark.png"
    _save_image(image_path, (20, 18, 16))

    result = estimate_text_contrast(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1}, "#ffffff")

    assert result["background_tone"] == "dark"
    assert result["recommended_text_tone"] == "light"
    assert result["contrast_ratio_estimate"] >= 4.5


def test_bright_background_recommends_plate_or_shadow(tmp_path):
    image_path = tmp_path / "bright.png"
    _save_image(image_path, (244, 238, 232))

    result = estimate_text_contrast(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1}, "#ffffff")

    assert result["background_tone"] == "bright"
    assert result["plate_required"] is True
    assert result["shadow_required"] is True
    assert "low_text_contrast" in result["warnings"]


def test_clipping_detection_catches_text_outside_canvas():
    result = validate_text_clipping({"canvas": {"width": 100, "height": 100}, "text_boxes": [{"bbox": (80, 80, 130, 110)}]})

    assert result["text_clipping_detected"] is True
    assert "text_box_outside_canvas" in result["warnings"]


def test_safe_area_complexity_warns_for_noisy_area(tmp_path):
    image = Image.new("RGB", (120, 120), (255, 255, 255))
    pixels = image.load()
    for x in range(120):
        for y in range(120):
            pixels[x, y] = (0, 0, 0) if (x + y) % 2 == 0 else (255, 255, 255)
    image_path = tmp_path / "noisy.png"
    image.save(image_path)

    result = validate_text_safe_area(str(image_path), {"x": 0, "y": 0, "w": 1, "h": 1})

    assert result["safe_area_background_complexity"] > 0.45
    assert "safe_area_complex_background" in result["warnings"]


def test_validation_report_includes_overall_pass_and_warnings(tmp_path):
    image_path = tmp_path / "bright.png"
    _save_image(image_path, (250, 250, 250))

    result = build_copy_visual_validation_report(
        str(image_path),
        {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5},
        "#ffffff",
        {"canvas": {"width": 120, "height": 120}, "text_boxes": []},
        min_font_size=18,
    )

    assert "overall_pass" in result
    assert "warnings" in result
    assert result["overall_pass"] is False
    assert "font_size_too_small" in result["warnings"]
