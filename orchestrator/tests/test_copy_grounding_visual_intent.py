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
    assert ranking.scorecards[0].hard_blocked is True


def test_macaron_meat_product_drift_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="마카롱 컬렉션", subcopy="고기 메뉴처럼 든든한 식사 메뉴", cta="컬렉션 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.product_drift_terms
    assert ranking.scorecards[0].hard_blocked is True


def test_internal_enum_menu_discovery_is_hard_blocked():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="menu_discovery 마카롱", subcopy="product_first 전략", cta="컬렉션 보기")

    grounding = evaluate_copy_grounding(candidate, context=context)
    ranking = rank_copy_candidates([candidate], state={"context": context.model_dump()})

    assert grounding.internal_terms
    assert ranking.scorecards[0].hard_blocked is True


def test_generic_strategy_words_are_not_product_anchors():
    context = MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery")
    candidate = CopyCandidate(id="copy_1", headline="상담 가능한 서비스", subcopy="필요한 구성을 선택하세요", cta="")

    grounding = evaluate_copy_grounding(candidate, context=context, strategy=build_message_strategy(context))

    assert grounding.grounded is False
    assert grounding.product_terms_found == []
