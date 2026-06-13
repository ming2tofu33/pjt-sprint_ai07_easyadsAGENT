import json
from pathlib import Path


def _fixture() -> dict:
    path = Path(__file__).resolve().parents[2] / "apps/web/types/contracts/generation-job-interrupt.fixtures.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_interrupt_contract_option_question_matches_backend_shape():
    option_question = _fixture()["optionQuestion"]

    assert option_question["type"] == "option_question"
    assert option_question["option_question"]["field"] == "business_type"
    assert option_question["option_question"]["required"] is True
    assert option_question["option_question"]["options"][0] == {"id": "cafe", "label": "카페/디저트", "value": "cafe"}


def test_interrupt_contract_copy_candidate_selection_matches_backend_shape():
    copy_selection = _fixture()["copyCandidateSelection"]

    assert copy_selection["type"] == "copy_candidate_selection"
    assert copy_selection["recommended_candidate_id"] == "copy_1"
    assert copy_selection["copy_candidate_origin"] == "llm"
    assert copy_selection["candidates"][0]["id"] == "copy_1"


def test_interrupt_contract_custom_copy_input_matches_backend_shape():
    custom_copy = _fixture()["customCopyInput"]

    assert custom_copy["type"] == "custom_copy_input"
    assert custom_copy["fields"][0]["field"] == "user_custom_headline"
    assert custom_copy["fields"][0]["required"] is True


def test_interrupt_contract_copy_compliance_review_matches_backend_shape():
    compliance = _fixture()["copyComplianceReview"]

    assert compliance["type"] == "copy_compliance_review"
    assert compliance["status"] == "evidence_required"
    assert compliance["actions"][0] == {"id": "use_suggestion", "label": "안전한 문구로 수정", "available": True}
