"""Phase 3: compliance gate branch 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


def _state(business_type="cafe", headline="기분 좋은 딸기라떼"):
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
    state = _state(business_type="cafe", headline="기분 좋은 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "pass"
    assert update["copy_compliance_publication_ready"] is True
    assert update["copy_compliance_gate"]["publication_ready"] is True
    assert update["copy_compliance_gate"]["findings"] == []


def test_gate_warns_on_ambiguous():
    state = _state(business_type="cafe", headline="디톡스 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "warn"
    assert update["copy_compliance_publication_ready"] is True


def test_gate_blocks_medical_claim():
    state = _state(business_type="beauty_skincare", headline="여드름 치료 100% 보장")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "blocked"
    assert update["copy_compliance_publication_ready"] is False
    assert len(update["copy_compliance_gate"]["findings"]) >= 1


def test_gate_evidence_required_for_superlative():
    state = _state(business_type="cafe", headline="국내 1위 카페")
    update = copy_compliance_gate_node(state)
    assert update["copy_compliance_status"] == "evidence_required"
    assert update["copy_compliance_publication_ready"] is False


def test_gate_stores_gate_dict_in_state():
    state = _state(business_type="cafe", headline="기분 좋은 딸기라떼")
    update = copy_compliance_gate_node(state)
    gate = update["copy_compliance_gate"]
    assert isinstance(gate, dict)
    assert "status" in gate
    assert "findings" in gate
    assert "publication_ready" in gate
    assert "original_copy" in gate


def test_gate_sets_status_field():
    state = _state()
    update = copy_compliance_gate_node(state)
    assert update["status"] == "copy_compliance_checked"


def test_gate_does_not_modify_marketing_copy():
    state = _state(business_type="cafe", headline="독소 배출 딸기라떼")
    update = copy_compliance_gate_node(state)
    assert "marketing_copy" not in update


# ── copy_compliance_resolution_node ──────────────────────────


def _blocked_state():
    state = _state(business_type="beauty_skincare", headline="여드름 치료 100% 보장")
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
    assert update["status"] == "compliance_blocked"


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
    state = _state()
    state["copy_compliance_status"] = "pass"
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_warn_goes_to_copy_spec_parser():
    state = _state()
    state["copy_compliance_status"] = "warn"
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_none_goes_to_copy_spec_parser():
    state = _state()
    state["copy_compliance_status"] = None
    assert route_after_compliance_gate(state) == "copy_spec_parser"


def test_route_after_compliance_gate_evidence_required_goes_to_interrupt():
    state = _state()
    state["copy_compliance_status"] = "evidence_required"
    assert route_after_compliance_gate(state) == "copy_compliance_interrupt"


def test_route_after_compliance_gate_blocked_goes_to_interrupt():
    state = _state()
    state["copy_compliance_status"] = "blocked"
    assert route_after_compliance_gate(state) == "copy_compliance_interrupt"


def test_route_after_compliance_resolution_use_suggestion_to_copy_spec():
    state = _state()
    state["copy_compliance_gate"] = {"user_decision": "use_suggestion"}
    assert route_after_compliance_resolution(state) == "copy_spec_parser"


def test_route_after_compliance_resolution_submit_claim_to_copy_spec():
    state = _state()
    state["copy_compliance_gate"] = {"user_decision": "submit_claim"}
    assert route_after_compliance_resolution(state) == "copy_spec_parser"


def test_route_after_compliance_resolution_edit_manually_to_custom_copy():
    state = _state()
    state["copy_compliance_gate"] = {"user_decision": "edit_manually"}
    assert route_after_compliance_resolution(state) == "custom_copy_input"


def test_route_after_compliance_resolution_cancel_to_end():
    from langgraph.graph import END
    state = _state()
    state["copy_compliance_gate"] = {"user_decision": "cancel"}
    assert route_after_compliance_resolution(state) == END
