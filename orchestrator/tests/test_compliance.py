"""Consolidated tests (real physical merge of source files).

Merged from:
- orchestrator/tests/test_compliance_candidate_badge.py
- orchestrator/tests/test_compliance_classifier.py
- orchestrator/tests/test_compliance_gate_branch.py
- orchestrator/tests/test_compliance_precheck_result_payload.py
- orchestrator/tests/test_compliance_prompt_injection.py
- orchestrator/tests/test_compliance_rule_engine.py
- orchestrator/tests/test_compliance_rule_loader.py
- orchestrator/tests/test_compliance_schemas.py
- orchestrator/tests/test_compliance_service.py
"""


# ===== from test_compliance_candidate_badge.py =====
"""Phase 2: 카피 후보 배지 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext
from orchestrator.tests.factories.compliance_payloads import make_compliance_candidate
from orchestrator.tests.helpers.compliance import assert_compliance_badge, assert_compliance_record


def _state(business_type="restaurant", item_or_service="삼겹살", promotion_goal="reservation_cta"):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="suggest_candidates",
            context=MarketingContext(
                business_type=business_type,
                item_or_service=item_or_service,
                promotion_goal=promotion_goal,
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )


# ── 초기 상태 필드 존재 여부 ──────────────────────────────────────────────────

def test_initial_state_has_input_compliance_risk():
    state = _state()
    assert "input_compliance_risk" in state
    assert state["input_compliance_risk"] is None


def test_initial_state_has_copy_compliance():
    state = _state()
    assert "copy_compliance" in state
    assert state["copy_compliance"] == []


def test_initial_state_has_copy_compliance_status():
    state = _state()
    assert "copy_compliance_status" in state
    assert state["copy_compliance_status"] is None


def test_initial_state_copy_compliance_publication_ready_defaults_true():
    state = _state()
    assert "copy_compliance_publication_ready" in state
    assert state["copy_compliance_publication_ready"] is True


# ── _attach_compliance_badges() 직접 테스트 ──────────────────────────────────

def test_attach_compliance_badges_adds_badge_key():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [make_compliance_candidate(headline="기분 좋은 딸기라떼", subcopy="한 잔의 여유", cta="주문하기")]
    updated, _records, _status, _ready = _attach_compliance_badges(candidates, state)
    badge = updated[0]["metadata"]["compliance"]
    assert "status" in badge
    assert "finding_count" in badge
    assert "disabled" in badge


def test_attach_compliance_badges_safe_copy_returns_pass():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [make_compliance_candidate(headline="기분 좋은 딸기라떼", subcopy="한 잔의 여유", cta="주문하기")]
    updated, records, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert_compliance_badge(updated[0], status="pass", disabled=False)
    assert worst_status == "pass"
    assert pub_ready is True
    assert_compliance_record(records[0], candidate_id="copy_1", publication_ready=True)


def test_attach_compliance_badges_blocked_copy_sets_disabled():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [make_compliance_candidate(headline="독소 배출 그린 스무디")]
    updated, records, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert_compliance_badge(updated[0], status="blocked", disabled=True)
    assert worst_status == "blocked"
    assert pub_ready is False
    assert records[0]["finding_count"] >= 1


def test_attach_compliance_badges_evidence_required():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [make_compliance_candidate(headline="국내 1위 카페")]
    _, _, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert worst_status == "evidence_required"
    assert pub_ready is False


def test_attach_compliance_badges_worst_case_across_candidates():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [
        make_compliance_candidate(headline="맛있는 딸기라떼"),
        make_compliance_candidate(candidate_id="copy_2", headline="독소 배출 그린 스무디"),
    ]
    _, _, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert worst_status == "blocked"
    assert pub_ready is False


def test_attach_compliance_badges_record_count_matches_candidates():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="restaurant")
    candidates = [
        make_compliance_candidate(headline="삼겹살 한 판", cta="예약하기"),
        make_compliance_candidate(candidate_id="copy_2", headline="오늘 회식은 여기서", cta="예약 문의"),
    ]
    _, records, _, _ = _attach_compliance_badges(candidates, state)
    assert len(records) == 2
    assert_compliance_record(records[0], candidate_id="copy_1")
    assert_compliance_record(records[1], candidate_id="copy_2")


# ── copy_candidate_generation_node 통합 ──────────────────────────────────────

from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node


def test_node_output_candidates_have_compliance_badge():
    update = copy_candidate_generation_node(_state())
    for candidate in update["copy_candidates"]:
        badge = candidate["metadata"]["compliance"]
        assert "status" in badge
        assert "finding_count" in badge
        assert "disabled" in badge


def test_node_output_badge_status_is_valid():
    update = copy_candidate_generation_node(_state())
    valid = {"pass", "warn", "evidence_required", "blocked"}
    for candidate in update["copy_candidates"]:
        assert candidate["metadata"]["compliance"]["status"] in valid


def test_node_output_safe_candidates_not_disabled():
    update = copy_candidate_generation_node(_state())
    for candidate in update["copy_candidates"]:
        badge = candidate["metadata"]["compliance"]
        assert badge["status"] == "pass"
        assert badge["disabled"] is False


def test_node_output_has_copy_compliance_list():
    update = copy_candidate_generation_node(_state())
    assert "copy_compliance" in update
    assert isinstance(update["copy_compliance"], list)
    assert len(update["copy_compliance"]) == len(update["copy_candidates"])


def test_node_output_copy_compliance_records_have_required_keys():
    update = copy_candidate_generation_node(_state())
    for record in update["copy_compliance"]:
        assert "candidate_id" in record
        assert "status" in record
        assert "finding_count" in record
        assert "publication_ready" in record
        assert "findings" in record


def test_node_output_has_copy_compliance_status():
    update = copy_candidate_generation_node(_state())
    assert "copy_compliance_status" in update
    assert update["copy_compliance_status"] in {"pass", "warn", "evidence_required", "blocked"}


def test_node_output_has_copy_compliance_publication_ready():
    update = copy_candidate_generation_node(_state())
    assert "copy_compliance_publication_ready" in update
    assert isinstance(update["copy_compliance_publication_ready"], bool)


def test_node_output_safe_restaurant_copy_is_publication_ready():
    update = copy_candidate_generation_node(_state())
    assert update["copy_compliance_publication_ready"] is True
    assert update["copy_compliance_status"] == "pass"


def test_node_output_compliance_record_candidate_ids_match():
    update = copy_candidate_generation_node(_state())
    candidate_ids = [c["id"] for c in update["copy_candidates"]]
    record_ids = [r["candidate_id"] for r in update["copy_compliance"]]
    assert candidate_ids == record_ids


def test_node_output_is_json_serializable():
    import json

    update = copy_candidate_generation_node(_state())
    json.dumps({
        "copy_candidates": update["copy_candidates"],
        "copy_compliance": update["copy_compliance"],
    }, ensure_ascii=False)


# ===== from test_compliance_classifier.py =====
"""IndustryClassifier — business_type → compliance domain 매핑 테스트."""


def _cls():
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    return IndustryClassifier()


def test_cafe_maps_to_food_and_general():
    domains = _cls().get_domains("cafe")
    assert "food" in domains
    assert "general_ad" in domains


def test_restaurant_maps_to_food():
    domains = _cls().get_domains("restaurant")
    assert "food" in domains


def test_beauty_skincare_maps_to_cosmetic():
    domains = _cls().get_domains("beauty_skincare")
    assert "cosmetic" in domains
    assert "general_ad" in domains


def test_hospital_maps_to_medical():
    domains = _cls().get_domains("hospital")
    assert "medical" in domains


def test_fitness_maps_to_general_ad():
    domains = _cls().get_domains("fitness")
    assert "general_ad" in domains


def test_unknown_type_falls_back_to_general_ad():
    domains = _cls().get_domains("unknown_xyz")
    assert domains == ["general_ad"]


def test_none_falls_back_to_general_ad():
    domains = _cls().get_domains(None)
    assert domains == ["general_ad"]


def test_all_food_business_types_include_food_domain():
    from orchestrator.app.compliance.industry_classifier import BUSINESS_TYPE_TO_DOMAIN

    food_types = [bt for bt, domains in BUSINESS_TYPE_TO_DOMAIN.items() if "food" in domains]
    assert len(food_types) >= 3


def test_get_domains_always_returns_list():
    cls = _cls()
    for biz_type in ["cafe", "hospital", "unknown", None]:
        result = cls.get_domains(biz_type)
        assert isinstance(result, list)
        assert len(result) > 0


# ===== from test_compliance_gate_branch.py =====
"""Phase 3: compliance gate branch 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state__test_compliance_gate_branch(business_type="cafe", headline="기분 좋은 딸기라떼"):
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(
                business_type=business_type,
                item_or_service="딸기라떼",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    s["marketing_copy"] = {
        "headline": headline,
        "subcopy": "한 잔의 여유",
        "cta": "주문하기",
        "hashtags": [],
        "metadata": {},
    }
    return s


# ── 초기 상태 필드 ────────────────────────────────────────────

def test_initial_state_has_copy_compliance_gate():
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(business_type="cafe", item_or_service="딸기라떼"),
        )
    )
    assert "copy_compliance_gate" in s
    assert s["copy_compliance_gate"] is None


def test_initial_state_has_copy_compliance_resolution():
    s = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode="auto_pilot",
            context=MarketingContext(business_type="cafe", item_or_service="딸기라떼"),
        )
    )
    assert "copy_compliance_resolution" in s
    assert s["copy_compliance_resolution"] is None


# ── copy_compliance_gate_node ─────────────────────────────────

from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_resolution_node,
)


def test_gate_passes_clean_copy():
    state = _state__test_compliance_gate_branch(business_type="cafe", headline="기분 좋은 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "pass"
    assert update["copy_compliance_publication_ready"] is True
    assert update["copy_compliance_gate"]["publication_ready"] is True
    assert update["copy_compliance_gate"]["findings"] == []


def test_gate_warns_on_ambiguous():
    state = _state__test_compliance_gate_branch(business_type="cafe", headline="디톡스 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "warn"
    assert update["copy_compliance_publication_ready"] is True


def test_gate_blocks_medical_claim():
    state = _state__test_compliance_gate_branch(business_type="beauty_skincare", headline="여드름 치료 100% 보장")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "blocked"
    assert update["copy_compliance_publication_ready"] is False
    assert len(update["copy_compliance_gate"]["findings"]) >= 1


def test_gate_evidence_required_for_superlative():
    state = _state__test_compliance_gate_branch(business_type="cafe", headline="국내 1위 카페")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "evidence_required"
    assert update["copy_compliance_publication_ready"] is False


def test_gate_stores_gate_dict_in_state():
    state = _state__test_compliance_gate_branch(business_type="cafe", headline="기분 좋은 딸기라떼")
    update = copy_compliance_gate_node(state)
    gate = update["copy_compliance_gate"]
    assert isinstance(gate, dict)
    assert "status" in gate
    assert "findings" in gate
    assert "publication_ready" in gate
    assert "original_copy" in gate


def test_gate_sets_status_field():
    state = _state__test_compliance_gate_branch()
    update = copy_compliance_gate_node(state)
    assert update["status"] == "copy_compliance_checked"


def test_gate_does_not_modify_marketing_copy():
    state = _state__test_compliance_gate_branch(business_type="cafe", headline="독소 배출 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert "marketing_copy" not in update


# ── copy_compliance_resolution_node ──────────────────────────


def _blocked_state():
    state = _state__test_compliance_gate_branch(business_type="beauty_skincare", headline="여드름 치료 100% 보장")
    state.update(copy_compliance_gate_node(state))
    return state


def test_resolution_use_suggestion_updates_marketing_copy():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "use_suggestion"}
    update = copy_compliance_resolution_node(state)
    assert "marketing_copy" in update
    assert update["marketing_copy"]["headline"] != "여드름 완치 보장"


def test_resolution_use_suggestion_sets_status_rewritten():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "use_suggestion"}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_status"] == "rewritten_by_user_choice"
    assert update["copy_compliance_publication_ready"] is True


def test_resolution_keep_original_sets_manual_review():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "keep_original_draft"}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_status"] == "manual_review_required"
    assert update["copy_compliance_publication_ready"] is False
    assert update["copy_compliance_gate"]["user_acknowledged_risk"] is True


def test_resolution_submit_claim_sets_manual_review():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "submit_claim", "evidence": {"text": "임상 자료 보유"}}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_status"] == "manual_review_required"
    assert update["copy_compliance_gate"]["evidence_submitted"] == [{"text": "임상 자료 보유"}]


def test_resolution_cancel_sets_compliance_blocked_status():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "cancel"}
    update = copy_compliance_resolution_node(state)
    assert update["status"] == "failed"
    assert update["error_info"]["error_code"] == "generation_job_cancelled_by_user"
    assert update["copy_compliance_gate"]["user_decision"] == "cancel"


def test_resolution_edit_manually_records_decision():
    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "edit_manually"}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_gate"]["user_decision"] == "edit_manually"
    assert "marketing_copy" not in update


def test_resolution_does_not_delete_original_copy():
    state = _blocked_state()
    assert state["copy_compliance_gate"]["original_copy"] is not None
    state["copy_compliance_resolution"] = {"action": "use_suggestion"}
    update = copy_compliance_resolution_node(state)
    assert update["copy_compliance_gate"].get("original_copy") is not None


# ── routers ───────────────────────────────────────────────────

from orchestrator.app.graph.routers import (
    route_after_compliance_gate,
    route_after_compliance_resolution,
)


def test_route_after_compliance_gate_pass_goes_to_copy_spec_parser():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_status"] = "pass"
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_warn_goes_to_copy_spec_parser():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_status"] = "warn"
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_none_goes_to_copy_spec_parser():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_status"] = None
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_evidence_required_goes_to_interrupt():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_status"] = "evidence_required"
    assert route_after_compliance_gate(state) == "copy_compliance_interrupt"


def test_route_after_compliance_gate_blocked_goes_to_interrupt():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_status"] = "blocked"
    assert route_after_compliance_gate(state) == "copy_compliance_interrupt"


def test_route_after_compliance_resolution_use_suggestion_to_copy_spec():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_gate"] = {"user_decision": "use_suggestion"}
    assert route_after_compliance_resolution(state) == "copy_spec_parser"


def test_route_after_compliance_resolution_submit_claim_to_copy_spec():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_gate"] = {"user_decision": "submit_claim"}
    assert route_after_compliance_resolution(state) == "copy_spec_parser"


def test_route_after_compliance_resolution_edit_manually_to_custom_copy():
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_gate"] = {"user_decision": "edit_manually"}
    assert route_after_compliance_resolution(state) == "custom_copy_input"


def test_route_after_compliance_resolution_cancel_to_end():
    from langgraph.graph import END
    state = _state__test_compliance_gate_branch()
    state["copy_compliance_gate"] = {"user_decision": "cancel"}
    assert route_after_compliance_resolution(state) == END


def test_resolution_cancel_routes_to_end_after_node_update():
    from langgraph.graph import END

    state = _blocked_state()
    state["copy_compliance_resolution"] = {"action": "cancel"}
    update = copy_compliance_resolution_node(state)

    assert route_after_compliance_resolution({**state, **update}) == END


# ===== from test_compliance_precheck_result_payload.py =====
"""Phase 4: input_compliance_precheck_node + result payload copyCompliance 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state__test_compliance_precheck_result_payload(user_input="ready", business_type="cafe"):
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
    state = _state__test_compliance_precheck_result_payload(user_input="딸기라떼 신메뉴 광고")
    update = input_compliance_precheck_node(state)
    assert update["input_compliance_risk"] is None
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_detects_blocked_term():
    state = _state__test_compliance_precheck_result_payload(user_input="독소 배출 효과 있는 음료", business_type="cafe")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert risk is not None
    assert risk["detected"] is True
    assert "독소 배출" in risk["flagged_terms"]


def test_precheck_sets_safe_direction_for_food():
    state = _state__test_compliance_precheck_result_payload(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    assert "중심으로" in update["input_compliance_risk"]["safe_direction"]


def test_precheck_does_not_block_flow_on_risk():
    state = _state__test_compliance_precheck_result_payload(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    assert "input_compliance_risk" in update
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_status_on_clean_input():
    state = _state__test_compliance_precheck_result_payload(user_input="안전한 카페 광고")
    update = input_compliance_precheck_node(state)
    assert update["status"] == "input_compliance_prechecked"


def test_precheck_blocked_sets_domains():
    state = _state__test_compliance_precheck_result_payload(user_input="독소 배출 딸기라떼")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert "food" in risk["domains"]


def test_precheck_medical_domain_hint():
    state = _state__test_compliance_precheck_result_payload(user_input="여드름 치료 100% 보장", business_type="beauty_skincare")
    update = input_compliance_precheck_node(state)
    risk = update["input_compliance_risk"]
    assert risk is not None
    assert risk["detected"] is True
    assert "케어" in risk["safe_direction"] or "상담" in risk["safe_direction"]


# ── result payload copyCompliance ────────────────────────────

from orchestrator.app.llm.nodes.result import result_node


def _result_state(copy_compliance_status="pass", gate=None, publication_ready=True):
    s = _state__test_compliance_precheck_result_payload()
    s["copy_compliance_gate"] = gate or {"findings": [], "publication_ready": True}
    s["copy_compliance_status"] = copy_compliance_status
    s["copy_compliance_publication_ready"] = publication_ready
    s["t2i_result"] = {"image_paths": ["/tmp/fake_result.png"]}
    s["final_image_path"] = "/tmp/fake_result.png"
    return s


def test_result_payload_has_copy_compliance_key():
    s = _result_state()
    update = result_node(s)
    assert update["result_payload"]["compliance"] is not None


def test_result_payload_copy_compliance_pass():
    s = _result_state(copy_compliance_status="pass", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["compliance"]
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
    cc = update["result_payload"]["compliance"]
    assert cc["publicationReady"] is False
    assert cc["userAcknowledgedRisk"] is True
    assert cc["findingCount"] == 1
    assert cc["userDecision"] == "keep_original_draft"


def test_result_payload_copy_compliance_warn():
    s = _result_state(copy_compliance_status="warn", publication_ready=True)
    update = result_node(s)
    cc = update["result_payload"]["compliance"]
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
    cc = update["result_payload"]["compliance"]
    assert len(cc["findings"]) == 1
    finding = cc["findings"][0]
    assert finding["matchedText"] == "1위"
    assert finding["legalBasis"][0]["lawName"] == "표시·광고의 공정화에 관한 법률"
    assert finding["suggestedText"] == "고객 만족 코칭 프로그램"


# ===== from test_compliance_prompt_injection.py =====
"""Phase 5: ComplianceService.get_rules_for_domains + metadata compliance 주입 테스트."""
from orchestrator.app.compliance.service import ComplianceService
from orchestrator.app.compliance.rule_engine import PatternMatcher
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
from orchestrator.app.compliance.industry_classifier import IndustryClassifier


def _svc() -> ComplianceService:
    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── get_rules_for_domains ────────────────────────────────────

def test_get_rules_for_domains_returns_food_rules():
    svc = _svc()
    food_rules = svc.get_rules_for_domains(["food"])
    assert len(food_rules) > 0
    assert all(r.domain == "food" for r in food_rules)


def test_get_rules_for_domains_returns_cosmetic_rules():
    svc = _svc()
    rules = svc.get_rules_for_domains(["cosmetic"])
    assert len(rules) > 0
    assert all(r.domain == "cosmetic" for r in rules)


def test_get_rules_for_domains_empty_returns_empty():
    svc = _svc()
    rules = svc.get_rules_for_domains([])
    assert rules == []


def test_get_rules_for_domains_multi_domain():
    svc = _svc()
    rules = svc.get_rules_for_domains(["food", "general_ad"])
    domains = {r.domain for r in rules}
    assert "food" in domains
    assert "general_ad" in domains


# ── build_copy_generation_metadata compliance 주입 ─────────

from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata


def test_build_copy_generation_metadata_has_compliance_for_food():
    state = {"context": {"business_type": "cafe", "item_or_service": "딸기라떼"}}
    metadata = build_copy_generation_metadata(state)
    constraints = metadata["constraints"]
    assert "compliance" in constraints


def test_compliance_blocked_terms_for_food_business():
    state = {"context": {"business_type": "cafe"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    blocked = compliance["blocked_terms"]
    assert any(term in blocked for term in ["독소 배출", "붓기 제거", "체지방 감소"])


def test_compliance_domains_for_beauty_skincare():
    state = {"context": {"business_type": "beauty_skincare"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    assert "cosmetic" in compliance["domains"]
    assert len(compliance["blocked_terms"]) > 0


def test_no_compliance_without_business_type():
    state = {"context": {}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"].get("compliance")
    assert compliance is None or compliance == {}


def test_compliance_has_safe_direction():
    state = {"context": {"business_type": "cafe"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    assert isinstance(compliance["safe_direction"], list)
    assert len(compliance["safe_direction"]) > 0


def test_existing_constraints_not_overwritten():
    state = {
        "context": {"business_type": "cafe"},
        "tone_binding_output": {"forbidden_claims": ["특허 성분"], "channel_copy_rules": [], "copy_constraints": []},
    }
    metadata = build_copy_generation_metadata(state)
    constraints = metadata["constraints"]
    assert "특허 성분" in constraints["forbidden_claims"]
    assert "compliance" in constraints


# ===== from test_compliance_rule_engine.py =====
"""PatternMatcher — scan() 및 aggregate_status() 테스트."""


def _matcher():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    return PatternMatcher(load_rules())


# ── scan(): 매칭 기본 ─────────────────────────────────────────────────────────

def test_scan_returns_empty_for_safe_copy():
    findings = _matcher().scan(
        {"headline": "기분 좋은 딸기라떼 한 잔"},
        domains=["food", "general_ad"],
    )
    assert findings == []


def test_scan_detects_block_pattern_in_headline():
    findings = _matcher().scan(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) == 1
    assert findings[0].severity == "block"
    assert findings[0].matched_text == "독소 배출"
    assert findings[0].field == "headline"


def test_scan_detects_warn_pattern():
    findings = _matcher().scan(
        {"headline": "디톡스 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "warn" for f in findings)


def test_scan_detects_evidence_required_pattern():
    findings = _matcher().scan(
        {"headline": "국내 1위 카페"},
        domains=["general_ad"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "evidence_required" for f in findings)


def test_scan_checks_subcopy_field():
    findings = _matcher().scan(
        {"headline": "안전한 헤드라인", "subcopy": "독소 배출 효과"},
        domains=["food"],
    )
    assert any(f.field == "sub_copy" for f in findings)


def test_scan_checks_cta_field():
    findings = _matcher().scan(
        {"headline": "안전한 문구", "cta": "독소 배출"},
        domains=["food"],
    )
    assert any(f.field == "cta" for f in findings)


def test_scan_only_applies_rules_matching_domain():
    """food 도메인 규칙은 general_ad만 요청하면 적용되지 않아야 한다."""
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["general_ad"],
    )
    food_block = [f for f in findings if f.rule_id == "KR-FOOD-MEDICAL-CLAIM-001"]
    assert food_block == []


def test_scan_finding_has_legal_basis_for_block_rule():
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["food"],
    )
    block_findings = [f for f in findings if f.severity == "block"]
    assert len(block_findings) > 0
    assert len(block_findings[0].legal_basis) > 0
    assert block_findings[0].legal_basis[0].law_name != ""


def test_scan_finding_has_rule_id():
    findings = _matcher().scan(
        {"headline": "독소 배출"},
        domains=["food"],
    )
    assert all(f.rule_id is not None for f in findings)


def test_scan_finding_ids_are_unique():
    findings = _matcher().scan(
        {"headline": "독소 배출", "subcopy": "면역력 강화"},
        domains=["food"],
    )
    ids = [f.finding_id for f in findings]
    assert len(ids) == len(set(ids)), "finding_id가 중복됨"


# ── aggregate_status() ────────────────────────────────────────────────────────

def test_aggregate_status_empty_returns_pass():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    assert aggregate_status([]) == "pass"


def test_aggregate_status_warn_returns_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [ComplianceFinding(finding_id="x", field="headline", severity="warn", matched_text="디톡스", reason="test")]
    assert aggregate_status(findings) == "warn"


def test_aggregate_status_block_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="w"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="b"),
    ]
    assert aggregate_status(findings) == "blocked"


def test_aggregate_status_evidence_required_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="w"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="evidence_required", matched_text="1위", reason="e"),
    ]
    assert aggregate_status(findings) == "evidence_required"


def test_aggregate_status_block_wins_over_evidence_required():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="evidence_required", matched_text="1위", reason="e"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="b"),
    ]
    assert aggregate_status(findings) == "blocked"


# ===== from test_compliance_rule_loader.py =====
"""rule_loader.py — YAML 로딩 및 계약 검증 테스트."""


def test_load_legal_basis_returns_dict():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert isinstance(basis, dict)
    assert len(basis) > 0


def test_legal_basis_has_expected_keys():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert "KR-FOOD-AD-8" in basis
    assert "KR-FAIR-AD-3" in basis


def test_legal_basis_entry_has_law_name():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    entry = basis["KR-FOOD-AD-8"]
    assert entry.law_name != ""
    assert entry.article != ""


def test_load_rules_returns_list():
    from orchestrator.app.compliance.rule_loader import load_rules

    rules = load_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 3


def test_rules_have_required_fields():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.schemas import ComplianceRule

    for rule in load_rules():
        assert isinstance(rule, ComplianceRule)
        assert rule.rule_id != ""
        assert rule.severity in {"warn", "evidence_required", "block"}
        assert len(rule.patterns) > 0


def test_rules_legal_basis_ref_resolved():
    """legal_basis_ref key가 법령 메타데이터로 실제로 연결되는지 확인."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.legal_basis_ref is not None:
            assert rule.legal_basis_ref.law_name != "", (
                f"{rule.rule_id}: legal_basis_ref.key가 legal_basis_kr_v1.yaml에 없음"
            )


def test_no_duplicate_rule_ids():
    from orchestrator.app.compliance.rule_loader import load_rules

    ids = [r.rule_id for r in load_rules()]
    assert len(ids) == len(set(ids)), f"중복 rule_id: {[x for x in ids if ids.count(x) > 1]}"


def test_yaml_contract_block_rules_have_examples():
    """block 규칙은 반드시 examples가 있어야 suggested_copy를 생성할 수 있다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "block":
            assert len(rule.examples) > 0, f"{rule.rule_id}: block 규칙에 examples 누락"


def test_yaml_contract_warn_rules_have_hitl_question():
    """warn 규칙은 사용자에게 맥락 확인 질문이 있어야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "warn":
            assert rule.hitl_question, f"{rule.rule_id}: warn 규칙에 hitl_question 누락"


def test_yaml_contract_evidence_required_rules_have_requirements():
    """evidence_required 규칙은 어떤 근거를 제출해야 하는지 명시해야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "evidence_required":
            assert len(rule.evidence_requirements) > 0, (
                f"{rule.rule_id}: evidence_required 규칙에 evidence_requirements 누락"
            )


def test_yaml_contract_all_rules_have_embedding_text():
    """RAG 확장 준비: embedding_text 없으면 벡터 인덱싱 불가."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        assert rule.embedding_text.strip(), f"{rule.rule_id}: embedding_text 누락"


# ===== from test_compliance_schemas.py =====
"""schemas.py import + 기본 인스턴스 생성 테스트."""


def test_compliance_finding_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceFinding

    f = ComplianceFinding(
        finding_id="test-001",
        field="headline",
        severity="block",
        matched_text="독소 배출",
        reason="식품 의료 효능 주장",
    )
    assert f.finding_id == "test-001"
    assert f.detection_method == "pattern"
    assert f.confidence == 1.0
    assert f.rag_context is None


def test_compliance_rewrite_candidate_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceRewriteCandidate

    candidate = ComplianceRewriteCandidate(
        text="정성껏 준비한 고기 한 접시",
        rationale="최상급 표현을 제거하고 상품 맥락을 유지했습니다.",
    )

    assert candidate.text == "정성껏 준비한 고기 한 접시"
    assert candidate.rationale.startswith("최상급")


def test_compliance_validated_suggestion_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceValidatedSuggestion

    suggestion = ComplianceValidatedSuggestion(
        id="suggestion_1",
        text="정성껏 준비한 고기 한 접시",
        validation_status="pass",
        rationale="재검수를 통과했습니다.",
    )

    assert suggestion.id == "suggestion_1"
    assert suggestion.validation_status == "pass"


def test_compliance_finding_accepts_suggestions():
    from orchestrator.app.compliance.schemas import ComplianceFinding, ComplianceValidatedSuggestion

    finding = ComplianceFinding(
        finding_id="finding_1",
        field="headline",
        rule_id="KR-GENERAL-SUPERLATIVE-001",
        severity="evidence_required",
        matched_text="최고",
        reason="실증 없는 최상급 표현",
        suggestions=[
            ComplianceValidatedSuggestion(
                id="suggestion_1",
                text="좋은 고기",
                validation_status="pass",
                rationale="위험 표현을 완화했습니다.",
            )
        ],
    )

    assert finding.suggestions[0].text == "좋은 고기"


def test_compliance_rewrite_plan_and_attempts_are_serialized():
    from orchestrator.app.compliance.schemas import (
        ComplianceFinding,
        ComplianceRewritePlan,
        CopyComplianceState,
    )

    plan = ComplianceRewritePlan(
        rule_id="KR-GENERAL-SUPERLATIVE-001",
        field="headline",
        matched_text="최고",
        strategy="soften_superlative",
        instruction="최상급 표현을 완화합니다.",
    )
    state = CopyComplianceState(
        status="evidence_required",
        findings=[
            ComplianceFinding(
                finding_id="finding_1",
                field="headline",
                rule_id="KR-GENERAL-SUPERLATIVE-001",
                severity="evidence_required",
                matched_text="최고",
                reason="실증 없는 최상급 표현",
                rewrite_plan=plan,
            )
        ],
        rewrite_attempts=[
            {"rule_id": "KR-GENERAL-SUPERLATIVE-001", "validated_count": 1}
        ],
        publication_ready=False,
    )

    payload = state.model_dump(mode="json")
    assert payload["findings"][0]["rewrite_plan"]["strategy"] == "soften_superlative"
    assert payload["rewrite_attempts"][0]["validated_count"] == 1


def test_compliance_rewrite_plan_rejects_unknown_copy_field():
    import pytest
    from pydantic import ValidationError

    from orchestrator.app.compliance.schemas import ComplianceRewritePlan

    with pytest.raises(ValidationError):
        ComplianceRewritePlan(
            rule_id="KR-GENERAL-SUPERLATIVE-001",
            field="body",
            matched_text="최고",
            strategy="soften_superlative",
            instruction="최상급 표현을 완화합니다.",
        )


def test_copy_compliance_state_defaults():
    from orchestrator.app.compliance.schemas import CopyComplianceState

    state = CopyComplianceState(status="pass")
    assert state.findings == []
    assert state.publication_ready is True
    assert state.user_acknowledged_risk is False


# ===== from test_compliance_service.py =====
"""ComplianceService end-to-end 테스트.

get_compliance_service()의 lru_cache 오염을 막기 위해
모든 테스트에서 _svc__test_compliance_service()로 직접 인스턴스를 생성한다.
"""


def _svc__test_compliance_service():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    from orchestrator.app.compliance.service import ComplianceService

    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── status 반환값 ──────────────────────────────────────────────────────────────

def test_safe_copy_returns_pass():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "기분 좋은 딸기라떼 한 잔", "subcopy": "오늘의 카페 타임"},
        business_type="cafe",
    )
    assert result.status == "pass"


def test_food_ambiguous_returns_warn():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "디톡스 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "warn"


def test_food_medical_claim_returns_blocked():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "blocked"


def test_superlative_returns_evidence_required():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "국내 1위 카페"},
        business_type="cafe",
    )
    assert result.status == "evidence_required"


# ── publication_ready 불변 조건 ────────────────────────────────────────────────

def test_pass_is_publication_ready():
    result = _svc__test_compliance_service().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is True


def test_warn_is_publication_ready():
    """warn은 논블로킹이므로 게시 가능해야 한다."""
    result = _svc__test_compliance_service().check_copy({"headline": "디톡스 딸기라떼"}, business_type="cafe")
    assert result.status == "warn"
    assert result.publication_ready is True


def test_evidence_required_is_not_publication_ready():
    result = _svc__test_compliance_service().check_copy({"headline": "국내 1위 카페"}, business_type="cafe")
    assert result.publication_ready is False


def test_blocked_is_not_publication_ready():
    result = _svc__test_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is False


# ── original_copy 보존 ─────────────────────────────────────────────────────────

def test_original_copy_is_stored_unchanged():
    original = {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}
    result = _svc__test_compliance_service().check_copy(original, business_type="cafe")
    assert result.original_copy == {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}


def test_original_copy_is_independent_from_input():
    """result.original_copy 수정이 입력 dict에 영향 없어야 한다."""
    original = {"headline": "독소 배출 딸기라떼"}
    result = _svc__test_compliance_service().check_copy(original, business_type="cafe")
    result.original_copy["headline"] = "변경됨"
    assert original["headline"] == "독소 배출 딸기라떼"


# ── suggested_copy ─────────────────────────────────────────────────────────────

def test_blocked_copy_has_suggested_copy():
    result = _svc__test_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is not None
    assert result.suggested_copy.get("headline") != "독소 배출 딸기라떼"


def test_superlative_suggestion_preserves_original_product_context():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "최고다 고기!", "subcopy": "맛도 좋고 보기도 좋은 1등급 고기"},
        business_type="restaurant",
    )

    assert result.status == "evidence_required"
    assert result.suggested_copy is not None
    suggested_headline = result.suggested_copy.get("headline", "")
    assert "고기" in suggested_headline
    assert "최고" not in suggested_headline
    assert "고객 만족 코칭 프로그램" not in suggested_headline


def test_superlative_finding_suggested_text_uses_contextual_rewrite():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "최고다 고기!", "subcopy": "맛도 좋고 보기도 좋은 1등급 고기"},
        business_type="restaurant",
    )

    finding = result.findings[0]
    assert finding.matched_text == "최고"
    assert finding.suggested_text is not None
    assert "고기" in finding.suggested_text
    assert "최고" not in finding.suggested_text
    assert "고객 만족 코칭 프로그램" not in finding.suggested_text


def test_pass_copy_has_no_suggested_copy():
    result = _svc__test_compliance_service().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is None


# ── findings 내용 ──────────────────────────────────────────────────────────────

def test_findings_detection_method_is_pattern():
    result = _svc__test_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.detection_method == "pattern" for f in result.findings)


def test_findings_confidence_is_1_for_pattern():
    result = _svc__test_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.confidence == 1.0 for f in result.findings)


def test_findings_rag_context_is_none_in_v1():
    result = _svc__test_compliance_service().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.rag_context is None for f in result.findings)


# ── 업종 fallback ─────────────────────────────────────────────────────────────

def test_unknown_business_type_uses_general_ad_rules():
    result = _svc__test_compliance_service().check_copy({"headline": "국내 1위 서비스"}, business_type="unknown_xyz")
    assert result.status == "evidence_required"


def test_none_business_type_uses_general_ad_rules():
    result = _svc__test_compliance_service().check_copy({"headline": "국내 1위 서비스"}, business_type=None)
    assert result.status == "evidence_required"


# ── get_compliance_service() singleton ────────────────────────────────────────

def test_get_compliance_service_returns_working_instance():
    from orchestrator.app.compliance.service import get_compliance_service

    svc = get_compliance_service()
    result = svc.check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.status == "pass"


# ── fitness 도메인 ─────────────────────────────────────────────────────────────

def test_fitness_guarantee_is_evidence_required():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "4주 만에 10kg 감량 보장"},
        business_type="fitness",
    )
    assert result.status == "evidence_required"


# ── medical 도메인 ─────────────────────────────────────────────────────────────

def test_medical_treatment_guarantee_is_blocked():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="hospital",
    )
    assert result.status == "blocked"


def test_medical_before_after_is_blocked():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "Before & After로 확인하는 시술 효과"},
        business_type="hospital",
    )
    assert result.status == "blocked"


# ── cosmetic 도메인 ────────────────────────────────────────────────────────────

def test_cosmetic_medical_claim_is_blocked():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "여드름 치료 100% 보장"},
        business_type="beauty_skincare",
    )
    assert result.status == "blocked"


# ── 도메인 격리: 다른 업종엔 medical 규칙 적용 안 됨 ─────────────────────────────

def test_medical_rule_does_not_apply_to_cafe():
    result = _svc__test_compliance_service().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="cafe",
    )
    medical_findings = [f for f in result.findings if f.rule_id and "MEDICAL" in f.rule_id]
    assert medical_findings == []
