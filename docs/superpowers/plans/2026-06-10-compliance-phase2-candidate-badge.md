# Compliance Phase 2 — Candidate Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 각 카피 후보에 규정 준수 배지(`metadata.compliance`)를 첨부하고, `MarketingState`에 집계 결과 3개 필드를 추가한다.

**Architecture:** `copy_candidate_generation_node`가 후보 리스트를 직렬화한 직후 `_attach_compliance_badges()`를 호출한다. 이 헬퍼는 `ComplianceService.check_copy()`를 후보별로 호출하고, 각 `candidate["metadata"]["compliance"]` 배지와 상태 필드 4개를 반환한다. 그래프 엣지·노드 추가 없음.

**Tech Stack:** Python 3.11+, LangGraph `TypedDict(total=False)`, Pydantic v2, pytest

---

## 변경 파일 목록

| 파일 | 역할 |
|------|------|
| `orchestrator/app/graph/state.py` | TypedDict에 4개 필드 추가 + 초기값 설정 |
| `orchestrator/app/llm/nodes/copy_candidates.py` | `_attach_compliance_badges()` 추가 + node 와이어링 |
| `orchestrator/tests/test_compliance_candidate_badge.py` | 신규 테스트 파일 (배지 구조·상태 필드·edge-case) |

---

## Task 1: MarketingState에 compliance 필드 4개 추가

**Files:**
- Modify: `orchestrator/app/graph/state.py:133` (TypedDict 선언부)
- Modify: `orchestrator/app/graph/state.py:310` (`create_initial_marketing_state` 초기화 dict)

- [ ] **Step 1-1: 실패 테스트 작성**

새 파일 `orchestrator/tests/test_compliance_candidate_badge.py`:

```python
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
```

- [ ] **Step 1-2: 테스트를 실행해 실패 확인**

```bash
cd /home/spai0710/pjt-sprint_ai07_easyadsAGENT
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py::test_initial_state_has_input_compliance_risk -v
```

Expected: `FAILED` — `KeyError` 또는 `AssertionError`.

- [ ] **Step 1-3: TypedDict에 4개 필드 추가**

`orchestrator/app/graph/state.py` 의 `MarketingState` 클래스, `copy_selection: dict[str, Any] | None` (line 133) 바로 뒤에 추가:

```python
    copy_selection: dict[str, Any] | None
    # compliance fields — Phase 2
    input_compliance_risk: str | None
    copy_compliance: list[dict[str, Any]]
    copy_compliance_status: str | None
    copy_compliance_publication_ready: bool
    custom_copy_input: dict[str, Any] | None
```

> 주의: `custom_copy_input` 줄은 이미 있으므로 그 앞에만 삽입한다. 즉 `copy_selection` 줄과 `custom_copy_input` 줄 사이에 세 줄을 끼워넣는다.

- [ ] **Step 1-4: `create_initial_marketing_state`에 초기값 추가**

같은 파일, `"copy_selection": None,` (line 310) 바로 뒤에:

```python
        "copy_selection": None,
        "input_compliance_risk": None,
        "copy_compliance": [],
        "copy_compliance_status": None,
        "copy_compliance_publication_ready": True,
        "custom_copy_input": None,
```

> 주의: `"custom_copy_input": None,` 줄은 이미 있으므로 그 앞에만 삽입한다.

- [ ] **Step 1-5: 테스트를 실행해 통과 확인**

```bash
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py \
    -k "initial_state" -v
```

Expected: 4개 PASSED.

- [ ] **Step 1-6: 기존 테스트 회귀 없음 확인**

```bash
python -m pytest orchestrator/tests/test_copy_candidates_branch.py orchestrator/tests/test_compliance_schemas.py orchestrator/tests/test_compliance_service.py -v
```

Expected: 전부 PASSED.

- [ ] **Step 1-7: 커밋**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_compliance_candidate_badge.py
git commit -m "feat(compliance): add 4 state fields for Phase 2 badge integration"
```

---

## Task 2: `_attach_compliance_badges()` 헬퍼 구현 + 노드 와이어링

**Files:**
- Modify: `orchestrator/app/llm/nodes/copy_candidates.py`

### 2-A: 헬퍼 함수 TDD

- [ ] **Step 2-1: 헬퍼 대상 테스트 작성**

`orchestrator/tests/test_compliance_candidate_badge.py` 에 추가:

```python
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
```

- [ ] **Step 2-2: 테스트 실행해 실패 확인**

```bash
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py \
    -k "attach_compliance_badges" -v
```

Expected: `ImportError` — `_attach_compliance_badges` not found.

- [ ] **Step 2-3: 헬퍼 함수 구현**

`orchestrator/app/llm/nodes/copy_candidates.py` 파일 끝부분(line 524 아래)에 추가:

```python
_COMPLIANCE_STATUS_RANK: dict[str, int] = {
    "pass": 0,
    "warn": 1,
    "evidence_required": 2,
    "blocked": 3,
}


def _attach_compliance_badges(
    candidates: list[dict[str, Any]],
    state: MarketingState,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, bool]:
    """각 후보 dict에 metadata.compliance 배지를 삽입하고 집계 상태를 반환한다.

    Returns:
        (updated_candidates, compliance_records, worst_status, all_publication_ready)
    """
    from orchestrator.app.compliance.service import get_compliance_service

    context = context_to_model(state.get("context"))
    svc = get_compliance_service()

    compliance_records: list[dict[str, Any]] = []
    worst_status = "pass"
    all_publication_ready = True

    for candidate in candidates:
        copy_dict: dict[str, Any] = {
            "headline": candidate.get("headline") or "",
            "subcopy": candidate.get("subcopy") or "",
            "cta": candidate.get("cta") or "",
        }
        result = svc.check_copy(copy_dict, context.business_type)
        candidate.setdefault("metadata", {})["compliance"] = {
            "status": result.status,
            "finding_count": len(result.findings),
            "disabled": not result.publication_ready,
        }
        compliance_records.append({
            "candidate_id": candidate.get("id"),
            "status": result.status,
            "finding_count": len(result.findings),
            "publication_ready": result.publication_ready,
            "findings": [f.model_dump() for f in result.findings],
        })
        if _COMPLIANCE_STATUS_RANK.get(result.status, 0) > _COMPLIANCE_STATUS_RANK.get(worst_status, 0):
            worst_status = result.status
        if not result.publication_ready:
            all_publication_ready = False

    return candidates, compliance_records, worst_status, all_publication_ready
```

- [ ] **Step 2-4: 헬퍼 테스트 통과 확인**

```bash
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py \
    -k "attach_compliance_badges" -v
```

Expected: 6개 PASSED.

### 2-B: 노드 와이어링 TDD

- [ ] **Step 2-5: 노드 레벨 테스트 작성**

`orchestrator/tests/test_compliance_candidate_badge.py` 에 추가:

```python
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
```

- [ ] **Step 2-6: 노드 테스트 실행해 실패 확인**

```bash
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py \
    -k "node_output" -v
```

Expected: `FAILED` — `copy_compliance` key 없음 또는 배지 없음.

- [ ] **Step 2-7: `copy_candidate_generation_node` 와이어링**

`orchestrator/app/llm/nodes/copy_candidates.py` 의 `copy_candidate_generation_node` 함수 return 블록을 교체:

현재 코드 (line 60–70):
```python
    candidate_origin = classify_copy_candidate_origin(output.metadata, llm_metadata)
    return {
        "copy_candidates": [candidate.model_dump() for candidate in candidates],
        "copy_candidate_origin": candidate_origin,
        "copywriting_output": output.model_dump(),
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "generating_copy_candidates",
    }
```

교체할 코드:
```python
    candidate_origin = classify_copy_candidate_origin(output.metadata, llm_metadata)
    serialized = [candidate.model_dump() for candidate in candidates]
    serialized, compliance_records, compliance_status, compliance_ready = _attach_compliance_badges(
        serialized, state
    )
    return {
        "copy_candidates": serialized,
        "copy_compliance": compliance_records,
        "copy_compliance_status": compliance_status,
        "copy_compliance_publication_ready": compliance_ready,
        "copy_candidate_origin": candidate_origin,
        "copywriting_output": output.model_dump(),
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "generating_copy_candidates",
    }
```

- [ ] **Step 2-8: 노드 테스트 통과 확인**

```bash
python -m pytest orchestrator/tests/test_compliance_candidate_badge.py -v
```

Expected: 전체 PASSED (초기 상태 4개 + 헬퍼 6개 + 노드 10개 = 20개).

- [ ] **Step 2-9: 전체 회귀 테스트**

```bash
python -m pytest orchestrator/tests/ -v --tb=short
```

Expected: 기존 60개 + 신규 20개 = 80개 전부 PASSED, 0 FAILED.

- [ ] **Step 2-10: 커밋**

```bash
git add orchestrator/app/llm/nodes/copy_candidates.py \
        orchestrator/tests/test_compliance_candidate_badge.py
git commit -m "feat(compliance): attach compliance badge to copy candidates (Phase 2)"
```

---

## 검증 체크리스트

Phase 2 완료 조건:

- [ ] `MarketingState` TypedDict에 `input_compliance_risk`, `copy_compliance`, `copy_compliance_status`, `copy_compliance_publication_ready` 4개 필드 존재
- [ ] `create_initial_marketing_state()` 가 4개 필드를 초기화 (빈 리스트, None, True)
- [ ] `copy_candidate_generation_node()` 반환 dict에 `copy_compliance`, `copy_compliance_status`, `copy_compliance_publication_ready` 포함
- [ ] 각 후보 dict의 `metadata["compliance"]`에 `status`, `finding_count`, `disabled` 존재
- [ ] `_attach_compliance_badges()` 가 worst-case status를 정확히 집계
- [ ] 기존 테스트(`test_copy_candidates_branch.py` 포함) 회귀 없음
- [ ] 신규 테스트 20개 PASSED

---

## 참고: 규칙-심각도 매핑

| severity (YAML) | status (CopyComplianceState) | publication_ready | disabled |
|----------------|------------------------------|-------------------|---------|
| `warn`         | `"warn"`                     | True              | False   |
| `evidence_required` | `"evidence_required"`   | False             | True    |
| `block`        | `"blocked"`                  | False             | True    |
| (없음)         | `"pass"`                     | True              | False   |
