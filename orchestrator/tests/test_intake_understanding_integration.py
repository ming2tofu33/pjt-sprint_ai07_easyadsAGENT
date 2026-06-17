from __future__ import annotations

from orchestrator.app.graph.nodes import validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def _validate(prompt: str) -> dict:
    state = create_initial_marketing_state(InitialMarketingRequest(user_input=prompt))
    return validator_node(state)


def test_validator_projects_business_subject_without_forcing_item_or_service():
    result = _validate("이번에 새로 오픈하는 프리미엄 뷰티샵 홍보 포스터 만들어줘. 고급스럽고 우아한 분위기면 좋겠어.")

    assert result["context"]["business_type"] is None
    assert result["context"]["item_or_service"] is None
    assert result["context"]["extra"]["ad_format"] == "poster"
    assert "business_type" in result["missing_fields"]
    assert result["intake_understanding_result"]["advertised_subject_type"] == "business"


def test_validator_keeps_open_domain_service_context():
    result = _validate("강남 영어회화반 직장인 대상 수강생 모집 배너 만들어줘. 평일 저녁 입문반 수업이야.")

    assert result["context"]["business_type"] == "education"
    assert result["context"]["item_or_service"] is not None
    assert result["context"]["target_persona"] == "office_workers"
    assert result["context"]["time_context"] == "weekday_evening"
    assert result["context"]["extra"]["ad_format"] == "banner"


def test_validator_marks_generic_beauty_as_ambiguous_not_missing_business_signal():
    result = _validate("뷰티 광고 만들어줘.")

    assert result["intake_understanding_result"]["business_candidate"] == "beauty"
    assert result["context"]["business_type"] is None
    assert "business_type" in result["missing_fields"]
    assert "beauty_subtype_ambiguous" in result["validator_metadata"]["intake_understanding"]["ambiguity_flags"]
