from __future__ import annotations

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.intake_understanding_service import (
    build_deterministic_intake_understanding,
    project_intake_to_context,
    understand_intake,
)
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _state(
    prompt: str,
    *,
    bundle: dict | None = None,
    context: dict | None = None,
) -> dict:
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=prompt))
    if bundle is not None:
        state["input_evidence_bundle"] = bundle
    if context is not None:
        state["context"] = {**state["context"], **context}
    return state


def test_deterministic_intake_uses_explicit_product_evidence_without_extra_vocab_rules():
    prompt = "Create a poster for Harbor Cafe and highlight our strawberry latte."
    result = build_deterministic_intake_understanding(
        _state(
            prompt,
            bundle={"user_text": prompt, "explicit_product_mentions": ["strawberry latte"]},
        ),
        prompt,
        hints={"business_type": "cafe", "item_or_service": None, "promotion_goal": "new_launch", "ad_format": "poster"},
    )

    assert result.business_candidate == "cafe"
    assert result.product_or_service_candidate == "strawberry latte"
    assert result.advertised_subject == "strawberry latte"
    assert result.advertised_subject_type == "product"
    assert result.tone_candidates == ()
    assert result.mood_candidates == ()
    assert result.target_candidates == ()
    assert result.confidence_by_field["product_or_service_candidate"] > 0


def test_deterministic_intake_separates_product_launch_from_store_opening():
    prompt = "\uc6b0\ub9ac \uce74\ud398 \ub538\uae30\ub77c\ub5bc \uc2e0\uba54\ub274 \uad11\uace0 \ub9cc\ub4e4\uc5b4\uc918"
    result = build_deterministic_intake_understanding(
        _state(
            prompt,
            bundle={"user_text": prompt, "explicit_product_mentions": ["\ub538\uae30\ub77c\ub5bc"]},
        ),
        prompt,
        hints={"business_type": "cafe", "item_or_service": None, "promotion_goal": None, "ad_format": "instagram_feed"},
    )

    assert result.advertised_subject_type == "product"
    assert result.campaign_intent_candidate == "new_menu_launch"


def test_understand_intake_skips_interpreter_when_deterministic_result_is_sufficient():
    prompt = "Create a banner for Harbor Cafe and highlight our strawberry latte."
    calls = {"count": 0}

    def fake_interpreter(state: dict, text: str):
        calls["count"] += 1
        return None, {"fallback_reason": "should_not_run"}

    result, trace = understand_intake(
        _state(prompt, bundle={"user_text": prompt, "explicit_product_mentions": ["strawberry latte"]}),
        prompt,
        deterministic_hints={
            "business_type": "cafe",
            "item_or_service": None,
            "promotion_goal": "new_launch",
            "ad_format": "banner",
        },
        brief_interpreter=fake_interpreter,
        brief_projector=lambda output, source_text: ({}, []),
    )

    assert calls["count"] == 0
    assert result.extraction_mode == "deterministic_only"
    assert trace["brief_interpreter"]["used"] is False
    assert trace["field_sources"]["product_or_service_candidate"] == "deterministic_parser"


def test_understand_intake_calls_interpreter_once_when_deterministic_context_is_incomplete():
    prompt = "Need an ad."
    calls = {"count": 0}

    def fake_interpreter(state: dict, text: str):
        calls["count"] += 1
        return (
            BriefInterpreterOutput(
                business_type="beauty",
                item_or_service="skin care package",
                promotion_goal="reservation",
                tone="premium",
                confidence=0.91,
            ),
            {"llm_attempted": True, "confidence": 0.91},
        )

    result, trace = understand_intake(
        _state(prompt, bundle={"user_text": prompt}),
        prompt,
        deterministic_hints={"business_type": None, "item_or_service": None, "promotion_goal": None, "ad_format": None},
        brief_interpreter=fake_interpreter,
        brief_projector=lambda output, source_text: (
            {
                "item_or_service": "skin care package",
                "promotion_goal": "reservation_cta",
                "brand_tone": "premium",
            },
            [],
        ),
    )
    updates, metadata = project_intake_to_context(result)

    assert calls["count"] == 1
    assert result.extraction_mode == "hybrid_structured_llm"
    assert result.business_candidate == "beauty"
    assert result.product_or_service_candidate == "skin care package"
    assert result.campaign_intent_candidate == "reservation_cta"
    assert updates["item_or_service"] == "skin care package"
    assert updates["promotion_goal"] == "reservation_cta"
    assert trace["brief_interpreter"]["used"] is True
    assert trace["field_sources"]["product_or_service_candidate"] == "structured_llm"
    assert metadata["domain_routing_result"].get("business_type") is None


def test_hybrid_intake_rejects_whole_prompt_item_and_routes_business_candidate_through_ssot():
    prompt = "Create a poster for our premium beauty salon opening and keep the tone elegant for working women in their 20s and 30s."

    def fake_interpreter(state: dict, text: str):
        return (
            BriefInterpreterOutput(
                business_type="beauty",
                item_or_service=prompt,
                promotion_goal="new_launch",
                tone="premium",
                confidence=0.93,
            ),
            {"llm_attempted": True, "confidence": 0.93},
        )

    result, _ = understand_intake(
        _state(prompt, bundle={"user_text": prompt}),
        prompt,
        deterministic_hints={"business_type": None, "item_or_service": None, "promotion_goal": None, "ad_format": "poster"},
        brief_interpreter=fake_interpreter,
        brief_projector=lambda output, source_text: (
            {
                "item_or_service": prompt,
                "promotion_goal": "store_opening",
                "brand_tone": "premium",
            },
            [],
        ),
    )
    updates, metadata = project_intake_to_context(result)

    assert result.business_candidate == "beauty"
    assert result.advertised_subject_type == "business"
    assert result.product_or_service_candidate is None
    assert result.campaign_intent_candidate == "store_opening"
    assert "item_or_service" not in updates
    assert "business_type" not in updates
    assert metadata["domain_routing_result"]["canonical_domain"] == "beauty"
    assert metadata["domain_routing_result"]["support_status"] == "needs_evidence"


def test_understand_intake_records_structured_fallback_without_retry():
    prompt = "Need an ad."
    calls = {"count": 0}

    def fake_interpreter(state: dict, text: str):
        calls["count"] += 1
        return None, {
            "llm_attempted": True,
            "fallback_used": True,
            "fallback_reason": "invalid_structured_output",
        }

    result, trace = understand_intake(
        _state(prompt, bundle={"user_text": prompt}),
        prompt,
        deterministic_hints={"business_type": None, "item_or_service": None, "promotion_goal": None, "ad_format": None},
        brief_interpreter=fake_interpreter,
        brief_projector=lambda output, source_text: ({}, []),
    )

    assert calls["count"] == 1
    assert result.extraction_mode == "deterministic_only"
    assert result.fallback_used is True
    assert result.fallback_reason == "invalid_structured_output"
    assert trace["fallback_used"] is True
    assert trace["fallback_reason"] == "invalid_structured_output"


def test_project_intake_to_context_keeps_launch_intent_out_of_legacy_promotion_goal():
    prompt = "\uc6b0\ub9ac \uce74\ud398 \ub538\uae30\ub77c\ub5bc \uc2e0\uba54\ub274 \uad11\uace0 \ub9cc\ub4e4\uc5b4\uc918"
    result = build_deterministic_intake_understanding(
        _state(
            prompt,
            bundle={"user_text": prompt, "explicit_product_mentions": ["\ub538\uae30\ub77c\ub5bc"]},
        ),
        prompt,
        hints={"business_type": "cafe", "item_or_service": None, "promotion_goal": None, "ad_format": "instagram_feed"},
    )

    updates, metadata = project_intake_to_context(result)

    assert updates["item_or_service"] == "\ub538\uae30\ub77c\ub5bc"
    assert "promotion_goal" not in updates
    assert metadata["unprojected_campaign_intent_candidate"] == "new_menu_launch"
