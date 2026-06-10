"""Phase 4: input_compliance_precheck_node + result payload copyCompliance 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(user_input="ready", business_type="cafe"):
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input=user_input,
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type=business_type,
                item_or_service="딸기라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    return s


# ── input_compliance_precheck_node ────────────────────────────

from orchestrator.app.llm.nodes.copy_compliance import input_compliance_precheck_node


def test_precheck_passes_clean_input():
    state = _state(user_input="딸기라떼 신메뉴 광고")
    update = input_compliance_precheck_node(state)
    assert update["input_compliance_risk"] is None
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_detects_blocked_term():
    state = _state(user_input="독소 배출 효과 있는 음료", business_type="cafe")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert risk is not None
    assert risk["detected"] is True
    assert "독소 배출" in risk["flagged_terms"]


def test_precheck_sets_safe_direction_for_food():
    state = _state(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    assert "중심으로" in update["input_compliance_risk"]["safe_direction"]


def test_precheck_does_not_block_flow_on_risk():
    state = _state(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    assert "input_compliance_risk" in update
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_status_on_clean_input():
    state = _state(user_input="안전한 카페 광고")
    update = input_compliance_precheck_node(state)
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_blocked_sets_domains():
    state = _state(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert "food" in risk["domains"]


def test_precheck_medical_domain_hint():
    state = _state(user_input="여드름 치료 100% 보장", business_type="beauty_skincare")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert risk is not None
    assert risk["detected"] is True
    assert "케어" in risk["safe_direction"] or "상담" in risk["safe_direction"]


# ── result payload copyCompliance ────────────────────────────

from orchestrator.app.llm.nodes.result import result_node


def _result_state(copy_compliance_status="pass", gate=None, publication_ready=True):
    s = _state()
    s["copy_compliance_gate"] = gate or {"findings": [], "publication_ready": True}
    s["copy_compliance_status"] = copy_compliance_status
    s["copy_compliance_publication_ready"] = publication_ready
    s["t2i_result"] = {"image_paths": ["/tmp/fake_result.png"]}
    s["final_image_path"] = "/tmp/fake_result.png"
    return s


def test_result_payload_has_copy_compliance_key():
    s = _result_state()
    update = result_node(s)
    assert "copyCompliance" in update["result_payload"]["metadata"]


def test_result_payload_copy_compliance_pass():
    s = _result_state(copy_compliance_status="pass", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["status"] == "pass"
    assert cc["publicationReady"] is True
    assert cc["findingCount"] == 0


def test_result_payload_copy_compliance_manual_review():
    gate = {
        "findings": [
            {
                "finding_id": "f1",
                "field": "headline",
                "matched_text": "독소 배출",
                "severity": "block",
                "detection_method": "pattern",
                "confidence": 1.0,
                "reason": "식품의 질병 예방·치료 또는 의학적 효능 암시",
                "legal_basis": [],
                "suggested_text": None,
            }
        ],
        "publication_ready": False,
        "user_decision": "keep_original_draft",
        "user_acknowledged_risk": True,
    }
    s = _result_state(
        copy_compliance_status="manual_review_required",
        gate=gate,
        publication_ready=False,
    )
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["publicationReady"] is False
    assert cc["userAcknowledgedRisk"] is True
    assert cc["findingCount"] == 1
    assert cc["userDecision"] == "keep_original_draft"


def test_result_payload_copy_compliance_warn():
    s = _result_state(copy_compliance_status="warn", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert cc["status"] == "warn"
    assert cc["publicationReady"] is True


def test_result_payload_copy_compliance_findings_serialized():
    gate = {
        "findings": [
            {
                "finding_id": "f1",
                "field": "headline",
                "matched_text": "1위",
                "severity": "evidence_required",
                "detection_method": "pattern",
                "confidence": 1.0,
                "reason": "실증 없는 최상급 표현",
                "legal_basis": [
                    {
                        "key": "KR-FAIR-AD-3",
                        "law_name": "표시·광고의 공정화에 관한 법률",
                        "article": "제3조",
                        "summary": "부당한 표시·광고 금지",
                    },
                ],
                "suggested_text": "고객 만족 코칭 프로그램",
            }
        ],
        "publication_ready": False,
    }
    s = _result_state(copy_compliance_status="evidence_required", gate=gate, publication_ready=False)
    update = result_node(s)
    cc = update["result_payload"]["metadata"]["copyCompliance"]
    assert len(cc["findings"]) == 1
    finding = cc["findings"][0]
    assert finding["matchedText"] == "1위"
    assert finding["legalBasis"][0]["lawName"] == "표시·광고의 공정화에 관한 법률"
    assert finding["suggestedText"] == "고객 만족 코칭 프로그램"
