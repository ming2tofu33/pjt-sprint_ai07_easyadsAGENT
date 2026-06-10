"""Phase 2: 카피 후보 배지 테스트."""
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext


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
    candidates = [
        {"id": "copy_1", "headline": "기분 좋은 딸기라떼", "subcopy": "한 잔의 여유", "cta": "주문하기", "metadata": {}},
    ]
    updated, _records, _status, _ready = _attach_compliance_badges(candidates, state)
    badge = updated[0]["metadata"]["compliance"]
    assert "status" in badge
    assert "finding_count" in badge
    assert "disabled" in badge


def test_attach_compliance_badges_safe_copy_returns_pass():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [
        {"id": "copy_1", "headline": "기분 좋은 딸기라떼", "subcopy": "한 잔의 여유", "cta": "주문하기", "metadata": {}},
    ]
    updated, records, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert updated[0]["metadata"]["compliance"]["status"] == "pass"
    assert updated[0]["metadata"]["compliance"]["disabled"] is False
    assert worst_status == "pass"
    assert pub_ready is True
    assert records[0]["candidate_id"] == "copy_1"
    assert records[0]["publication_ready"] is True


def test_attach_compliance_badges_blocked_copy_sets_disabled():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [
        {"id": "copy_1", "headline": "독소 배출 그린 스무디", "subcopy": None, "cta": None, "metadata": {}},
    ]
    updated, records, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    badge = updated[0]["metadata"]["compliance"]
    assert badge["status"] == "blocked"
    assert badge["disabled"] is True
    assert worst_status == "blocked"
    assert pub_ready is False
    assert records[0]["finding_count"] >= 1


def test_attach_compliance_badges_evidence_required():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [
        {"id": "copy_1", "headline": "국내 1위 카페", "subcopy": None, "cta": None, "metadata": {}},
    ]
    _, _, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert worst_status == "evidence_required"
    assert pub_ready is False


def test_attach_compliance_badges_worst_case_across_candidates():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="cafe")
    candidates = [
        {"id": "copy_1", "headline": "맛있는 딸기라떼", "subcopy": None, "cta": None, "metadata": {}},
        {"id": "copy_2", "headline": "독소 배출 그린 스무디", "subcopy": None, "cta": None, "metadata": {}},
    ]
    _, _, worst_status, pub_ready = _attach_compliance_badges(candidates, state)
    assert worst_status == "blocked"
    assert pub_ready is False


def test_attach_compliance_badges_record_count_matches_candidates():
    from orchestrator.app.llm.nodes.copy_candidates import _attach_compliance_badges

    state = _state(business_type="restaurant")
    candidates = [
        {"id": "copy_1", "headline": "삼겹살 한 판", "subcopy": None, "cta": "예약하기", "metadata": {}},
        {"id": "copy_2", "headline": "오늘 회식은 여기서", "subcopy": None, "cta": "예약 문의", "metadata": {}},
    ]
    _, records, _, _ = _attach_compliance_badges(candidates, state)
    assert len(records) == 2
    assert records[0]["candidate_id"] == "copy_1"
    assert records[1]["candidate_id"] == "copy_2"


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
