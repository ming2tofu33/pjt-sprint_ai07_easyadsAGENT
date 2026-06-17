from __future__ import annotations

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.intake_understanding_service import (
    build_deterministic_intake_understanding,
    project_intake_to_context,
    understand_intake,
)
from orchestrator.app.schemas.brief_llm import BriefInterpreterOutput
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _state(prompt: str) -> dict:
    return create_initial_marketing_state(InitialMarketingRequest(user_input=prompt))


def test_deterministic_intake_extracts_business_subject_without_inventing_item():
    prompt = "이번에 새로 오픈하는 프리미엄 뷰티샵 홍보 포스터 만들어줘. 고급스럽고 우아한 분위기면 좋겠어."
    result = build_deterministic_intake_understanding(
        _state(prompt),
        prompt,
        hints={"business_type": "beauty_salon", "item_or_service": None, "promotion_goal": None, "ad_format": "poster"},
    )

    assert result.business_candidate == "beauty_salon"
    assert result.advertised_subject == "프리미엄 뷰티샵"
    assert result.advertised_subject_type == "business"
    assert result.product_or_service_candidate is None
    assert result.ad_format_candidate == "poster"
    assert "premium" in result.tone_candidates
    assert "elegant" in result.mood_candidates


def test_deterministic_intake_preserves_service_phrase_and_context_clues():
    prompt = "강남 영어회화반 직장인 대상 수강생 모집 배너 만들어줘. 평일 저녁 입문반 수업이야."
    result = build_deterministic_intake_understanding(
        _state(prompt),
        prompt,
        hints={"business_type": None, "item_or_service": None, "promotion_goal": None, "ad_format": "banner"},
    )

    assert result.business_candidate == "education"
    assert result.product_or_service_candidate == "강남 영어회화반"
    assert result.advertised_subject_type == "service"
    assert result.campaign_intent_candidate == "student_recruitment"
    assert result.ad_format_candidate == "banner"
    assert "office_workers" in result.target_candidates
    assert "weekday_evening" in result.time_context
    assert "강남" in result.location_context


def test_deterministic_intake_separates_beauty_mood_from_cafe_business():
    prompt = "뷰티 감성으로 꾸민 카페의 딸기 라떼 포스터 만들어줘."
    result = build_deterministic_intake_understanding(
        _state(prompt),
        prompt,
        hints={"business_type": "cafe", "item_or_service": "딸기 라떼", "promotion_goal": None, "ad_format": "poster"},
    )

    assert result.business_candidate == "cafe"
    assert result.product_or_service_candidate == "딸기 라떼"
    assert result.advertised_subject_type == "product"
    assert result.mood_candidates == ("beauty_inspired",)


def test_hybrid_intake_reuses_brief_interpreter_without_actual_call():
    prompt = "광고 만들어줘"

    def fake_interpreter(state: dict, text: str):
        return (
            BriefInterpreterOutput(
                business_type="beauty",
                item_or_service="스킨케어 상담",
                promotion_goal="reservation",
                tone="premium",
                copy_generation_mode="suggest_candidates",
                confidence=0.91,
            ),
            {"llm_attempted": True, "confidence": 0.91},
        )

    def fake_projector(output: BriefInterpreterOutput, source_text: str):
        return (
            {
                "business_type": None,
                "item_or_service": "스킨케어 상담",
                "promotion_goal": "reservation_cta",
                "brand_tone": "premium",
                "copy_generation_mode": "suggest_candidates",
            },
            ["business_type_fallback_generic: ambiguous_beauty_subdomain"],
        )

    result, trace = understand_intake(
        _state(prompt),
        prompt,
        deterministic_hints={"business_type": None, "item_or_service": None, "promotion_goal": None, "ad_format": None},
        brief_interpreter=fake_interpreter,
        brief_projector=fake_projector,
    )
    updates, metadata = project_intake_to_context(result)

    assert result.business_candidate == "beauty"
    assert result.product_or_service_candidate == "스킨케어 상담"
    assert updates["item_or_service"] == "스킨케어 상담"
    assert updates["promotion_goal"] == "reservation_cta"
    assert "beauty_subtype_ambiguous" in metadata["ambiguity_flags"]
    assert trace["brief_interpreter"]["used"] is True
    assert trace["copy_generation_mode_candidate"] == "suggest_candidates"
