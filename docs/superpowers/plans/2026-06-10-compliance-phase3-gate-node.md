# Compliance Phase 3 — copy_compliance_gate 노드 + Graph 연결

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `copy_compliance_gate` 노드(+interrupt·resolution 2개)를 만들고 LangGraph에 연결한다. 선택된/생성된 `marketing_copy`를 규정 준수 관점에서 검사하고, 위반 시 HITL interrupt를 발생시킨다.

**Architecture:** 기존 `state_update_selected_copy`, `auto_pilot_copywriting`, `custom_copy_validation` → `copy_spec_parser` 엣지 3개를 `copy_compliance_gate`를 거치도록 변경한다. pass/warn이면 투명하게 통과, evidence_required/blocked이면 interrupt 발생 후 사용자 결정을 받아 분기한다. 그래프 엣지 변경이 있으므로 `test_marketing_graph_node_utilization.py`도 업데이트한다.

**Tech Stack:** Python 3.11+, LangGraph `interrupt()`, Pydantic v2, pytest

---

## 변경 파일 목록

| 파일 | 역할 |
|------|------|
| `orchestrator/app/graph/state.py` | `copy_compliance_gate`, `copy_compliance_resolution` 필드 추가 |
| `orchestrator/app/llm/nodes/copy_compliance.py` | **신규** — gate/interrupt/resolution 노드 3개 |
| `orchestrator/app/graph/routers.py` | `route_after_compliance_gate`, `route_after_compliance_resolution` 추가 |
| `orchestrator/app/graph/builder.py` | 노드 3개 추가, 엣지 3개 변경 + 신규 조건 엣지 |
| `orchestrator/tests/test_compliance_gate_branch.py` | **신규** — 노드 단위 테스트 |
| `orchestrator/tests/test_marketing_graph_node_utilization.py` | `TRACEABLE_NODE_ATTRS` 3개 추가, matrix 업데이트, 신규 시나리오 추가 |

> **Phase 3 State 필드 설계 주의:** Phase 2가 `copy_compliance: list[dict]`를 이미 사용한다.
> Phase 3는 **별도 필드**를 사용한다.
> - `copy_compliance_gate: dict[str, Any] | None` — gate가 `marketing_copy`를 검사한 결과
> - `copy_compliance_resolution: dict[str, Any] | None` — interrupt resume 페이로드
> - `copy_compliance_status` / `copy_compliance_publication_ready` — gate가 덮어씀 (Phase 2에서 초기화됨)

---

## Task 1: State 필드 2개 추가

**Files:**
- Modify: `orchestrator/app/graph/state.py:133` (TypedDict)
- Modify: `orchestrator/app/graph/state.py:315` (`create_initial_marketing_state` init dict)

- [ ] **Step 1-1: 실패 테스트 작성**

`orchestrator/tests/test_compliance_gate_branch.py` 생성:

```python
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
```

- [ ] **Step 1-2: 실패 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "initial_state" -v
```

Expected: `FAILED` — `KeyError`.

- [ ] **Step 1-3: TypedDict에 2개 필드 추가**

`orchestrator/app/graph/state.py`, `copy_compliance_publication_ready: bool` 아래에 삽입:

```python
    copy_compliance_publication_ready: bool
    copy_compliance_gate: dict[str, Any] | None
    copy_compliance_resolution: dict[str, Any] | None
    custom_copy_input: dict[str, Any] | None
```

> `custom_copy_input` 줄은 이미 있으므로 2개 줄만 삽입한다.

- [ ] **Step 1-4: initializer에 초기값 추가**

`orchestrator/app/graph/state.py`, `"copy_compliance_publication_ready": True,` 바로 아래에:

```python
        "copy_compliance_publication_ready": True,
        "copy_compliance_gate": None,
        "copy_compliance_resolution": None,
        "custom_copy_input": None,
```

> `"custom_copy_input": None,` 줄은 이미 있으므로 2개 줄만 삽입한다.

- [ ] **Step 1-5: 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "initial_state" -v
```

Expected: 2개 PASSED.

- [ ] **Step 1-6: 기존 테스트 회귀 없음 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_candidate_badge.py \
    orchestrator/tests/test_compliance_service.py -v --tb=short
```

Expected: 전부 PASSED.

- [ ] **Step 1-7: 커밋**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_compliance_gate_branch.py
git commit -m "feat(compliance): add copy_compliance_gate/resolution state fields (Phase 3)"
```

---

## Task 2: `copy_compliance.py` — 노드 3개 구현

**Files:**
- Create: `orchestrator/app/llm/nodes/copy_compliance.py`

### 2-A: Gate 노드 TDD

- [ ] **Step 2-1: Gate 노드 테스트 작성**

`orchestrator/tests/test_compliance_gate_branch.py`에 추가:

```python
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
    assert update["copy_compliance_publication_ready"] is True  # warn은 non-blocking


def test_gate_blocks_medical_claim():
    state = _state(business_type="beauty_skincare", headline="여드름 완치 보장")
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
    original_headline = state["marketing_copy"]["headline"]
    update = copy_compliance_gate_node(state)
    assert "marketing_copy" not in update  # gate는 marketing_copy를 바꾸지 않음
```

- [ ] **Step 2-2: 실패 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "gate" -v
```

Expected: `ImportError` — `copy_compliance` module not found.

- [ ] **Step 2-3: `copy_compliance.py` 파일 생성 — Gate 노드 구현**

`orchestrator/app/llm/nodes/copy_compliance.py`:

```python
"""Compliance gate 노드 구현.

copy_compliance_gate_node: marketing_copy를 검사. marketing_copy를 직접 수정하지 않는다.
copy_compliance_interrupt_node: evidence_required/blocked 시 HITL interrupt 발생.
copy_compliance_resolution_node: 사용자 결정을 처리해 다음 노드를 결정한다.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.compliance.service import get_compliance_service
from orchestrator.app.graph.state import MarketingState, context_to_model


def copy_compliance_gate_node(state: MarketingState) -> dict[str, Any]:
    copy = dict(state.get("marketing_copy") or {})
    business_type = context_to_model(state.get("context")).business_type
    svc = get_compliance_service()
    result = svc.check_copy(copy, business_type)
    return {
        "copy_compliance_gate": result.model_dump(),
        "copy_compliance_status": result.status,
        "copy_compliance_publication_ready": result.publication_ready,
        "status": "copy_compliance_checked",
    }


def copy_compliance_interrupt_node(state: MarketingState) -> dict[str, Any]:
    gate = dict(state.get("copy_compliance_gate") or {})
    findings = gate.get("findings") or []
    status = state.get("copy_compliance_status") or "evidence_required"

    actions = [
        {"id": "use_suggestion",      "label": "안전한 문구로 수정",          "available": True},
        {"id": "edit_manually",       "label": "직접 수정",                   "available": True},
        {"id": "submit_claim",        "label": "근거자료 제출",               "available": True},
        {"id": "keep_original_draft", "label": "위험을 인지하고 초안으로 계속", "available": status != "blocked"},
        {"id": "cancel",              "label": "생성 취소",                   "available": True},
    ]
    payload = {
        "type": "copy_compliance_review",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "status": status,
        "summary": _build_summary(findings),
        "findings": _serialize_findings(findings),
        "actions": actions,
    }
    resume_payload = interrupt(payload)
    return {
        "copy_compliance_gate": {**gate, "interrupt_payload": payload},
        "copy_compliance_resolution": resume_payload,
        "status": "waiting_compliance_decision",
    }


def copy_compliance_resolution_node(state: MarketingState) -> dict[str, Any]:
    resolution = dict(state.get("copy_compliance_resolution") or {})
    decision = resolution.get("action") or resolution.get("user_decision")
    gate = dict(state.get("copy_compliance_gate") or {})

    if decision == "use_suggestion":
        suggested = gate.get("suggested_copy")
        if suggested:
            return {
                "marketing_copy": suggested,
                "copy_compliance_gate": {**gate, "user_decision": "use_suggestion", "status": "rewritten_by_user_choice", "publication_ready": True},
                "copy_compliance_status": "rewritten_by_user_choice",
                "copy_compliance_publication_ready": True,
            }

    if decision == "submit_claim":
        evidence = resolution.get("evidence") or {}
        submitted = list(gate.get("evidence_submitted") or [])
        submitted.append(evidence)
        return {
            "copy_compliance_gate": {**gate, "user_decision": "submit_claim", "status": "manual_review_required", "publication_ready": False, "evidence_submitted": submitted},
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
        }

    if decision == "keep_original_draft":
        return {
            "copy_compliance_gate": {**gate, "user_decision": "keep_original_draft", "user_acknowledged_risk": True, "status": "manual_review_required", "publication_ready": False},
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
        }

    if decision == "cancel":
        return {"status": "compliance_blocked"}

    # edit_manually: router가 custom_copy_input으로 분기
    return {
        "copy_compliance_gate": {**gate, "user_decision": "edit_manually"},
    }


def _build_summary(findings: list[dict[str, Any]]) -> str:
    count = len(findings)
    if count == 0:
        return "광고 규제 검토를 통과했습니다."
    return f"광고 규제 위험 표현 {count}개가 발견되었습니다."


def _serialize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for f in findings:
        legal_basis = f.get("legal_basis") or []
        result.append({
            "finding_id": f.get("finding_id"),
            "field": f.get("field"),
            "matched_text": f.get("matched_text"),
            "severity": f.get("severity"),
            "detection_method": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "reason": f.get("reason"),
            "legal_basis": [
                {"key": b.get("key"), "law_name": b.get("law_name"), "article": b.get("article"), "summary": b.get("summary"), "chunk_id": b.get("chunk_id")}
                for b in legal_basis
            ],
            "suggested_text": f.get("suggested_text"),
            "evidence_requirements": f.get("evidence_requirements") or [],
            "hitl_question": f.get("hitl_question"),
            "rag_context": f.get("rag_context"),
        })
    return result
```

- [ ] **Step 2-4: Gate 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "gate" -v
```

Expected: 7개 PASSED.

### 2-B: Resolution 노드 TDD

- [ ] **Step 2-5: Resolution 노드 테스트 작성**

`orchestrator/tests/test_compliance_gate_branch.py`에 추가:

```python
# ── copy_compliance_resolution_node ──────────────────────────

def _blocked_state():
    state = _state(business_type="beauty_skincare", headline="여드름 완치 보장")
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
```

- [ ] **Step 2-6: Resolution 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "resolution" -v
```

Expected: 7개 PASSED.

- [ ] **Step 2-7: 커밋**

```bash
git add orchestrator/app/llm/nodes/copy_compliance.py \
        orchestrator/tests/test_compliance_gate_branch.py
git commit -m "feat(compliance): add copy_compliance gate/interrupt/resolution nodes (Phase 3)"
```

---

## Task 3: Routers 추가

**Files:**
- Modify: `orchestrator/app/graph/routers.py`

- [ ] **Step 3-1: Router 테스트 작성**

`orchestrator/tests/test_compliance_gate_branch.py`에 추가:

```python
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
```

- [ ] **Step 3-2: 실패 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "route_after_compliance" -v
```

Expected: `ImportError` — routers에 함수 없음.

- [ ] **Step 3-3: Routers 추가**

`orchestrator/app/graph/routers.py` 파일 끝에 추가 (기존 `from langgraph.graph import END` 사용):

```python
def route_after_compliance_gate(state: MarketingState) -> str:
    """pass / warn → copy_spec_parser로 투명 통과.
    evidence_required / blocked → interrupt 발생."""
    status = state.get("copy_compliance_status")
    if status in {None, "pass", "warn", "rewritten_by_user_choice"}:
        return "copy_spec_parser"
    return "copy_compliance_interrupt"


def route_after_compliance_resolution(state: MarketingState) -> str:
    """사용자 결정 후 다음 노드 결정."""
    gate = state.get("copy_compliance_gate") or {}
    decision = gate.get("user_decision")
    if decision == "cancel":
        return END
    if decision == "edit_manually":
        return "custom_copy_input"
    return "copy_spec_parser"
```

- [ ] **Step 3-4: Router 테스트 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py \
    -k "route_after_compliance" -v
```

Expected: 9개 PASSED.

- [ ] **Step 3-5: 전체 gate branch 테스트 통과**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_compliance_gate_branch.py -v
```

Expected: 25개 PASSED (초기 상태 2 + gate 7 + resolution 7 + router 9).

- [ ] **Step 3-6: 커밋**

```bash
git add orchestrator/app/graph/routers.py orchestrator/tests/test_compliance_gate_branch.py
git commit -m "feat(compliance): add route_after_compliance_gate/resolution routers"
```

---

## Task 4: builder.py 와이어링

**Files:**
- Modify: `orchestrator/app/graph/builder.py`

- [ ] **Step 4-1: import 추가**

`orchestrator/app/graph/builder.py` 상단 import 블록에 추가:

```python
from orchestrator.app.llm.nodes.copy_compliance import (
    copy_compliance_gate_node,
    copy_compliance_interrupt_node,
    copy_compliance_resolution_node,
)
```

그리고 routers import 줄에 2개 추가:

```python
from orchestrator.app.graph.routers import (
    route_by_entry_mode,
    route_after_input_assets,
    route_after_input_reference_template,
    route_after_reference_template_resolve,
    route_after_product_preprocess,
    route_after_validator_for_intake,
    route_after_validator_for_marketing,
    route_after_tone_binding,
    route_by_copy_presence,
    route_after_layout_refiner,
    route_after_t2i_generation,
    route_after_ocr_gate,
    route_after_compliance_gate,       # 추가
    route_after_compliance_resolution, # 추가
)
```

> 현재 `builder.py`의 routers import 구조를 확인하고 해당 리스트에 2개를 추가한다.

- [ ] **Step 4-2: 노드 3개 추가**

`orchestrator/app/graph/builder.py`, `no_copy_bypass` 노드 선언(line 87) 바로 뒤에:

```python
    graph.add_node("no_copy_bypass", no_copy_bypass_node)
    graph.add_node("copy_compliance_gate", copy_compliance_gate_node)
    graph.add_node("copy_compliance_interrupt", copy_compliance_interrupt_node)
    graph.add_node("copy_compliance_resolution", copy_compliance_resolution_node)
    graph.add_node("copy_spec_parser", copy_spec_parser_node)
```

> `copy_spec_parser` 노드 선언(line 88) 앞에 3개 줄을 삽입한다.

- [ ] **Step 4-3: 엣지 3개 변경 + 신규 조건 엣지 추가**

기존 코드 (line 151–155):

```python
    graph.add_edge("state_update_selected_copy", "copy_spec_parser")
    graph.add_edge("auto_pilot_copywriting", "copy_spec_parser")
    graph.add_edge("custom_copy_input", "custom_copy_validation")
    graph.add_edge("custom_copy_validation", "copy_spec_parser")
    graph.add_edge("no_copy_bypass", "copy_spec_parser")
```

교체할 코드:

```python
    graph.add_edge("state_update_selected_copy", "copy_compliance_gate")
    graph.add_edge("auto_pilot_copywriting", "copy_compliance_gate")
    graph.add_edge("custom_copy_input", "custom_copy_validation")
    graph.add_edge("custom_copy_validation", "copy_compliance_gate")
    graph.add_edge("no_copy_bypass", "copy_spec_parser")  # no_copy는 게이트 불필요
    graph.add_conditional_edges(
        "copy_compliance_gate",
        route_after_compliance_gate,
        {
            "copy_spec_parser": "copy_spec_parser",
            "copy_compliance_interrupt": "copy_compliance_interrupt",
        },
    )
    graph.add_edge("copy_compliance_interrupt", "copy_compliance_resolution")
    graph.add_conditional_edges(
        "copy_compliance_resolution",
        route_after_compliance_resolution,
        {
            "copy_spec_parser": "copy_spec_parser",
            "custom_copy_input": "custom_copy_input",
            END: END,
        },
    )
```

> `from langgraph.graph import END`가 `builder.py` 상단에 이미 있는지 확인한다. 없으면 추가.

- [ ] **Step 4-4: 기존 e2e 테스트가 pass/warn 케이스에서 통과하는지 확인**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/test_marketing_graph_e2e_mock.py -v --tb=short
```

Expected: 전부 PASSED. (restaurant/삼겹살 카피는 clean → compliance gate 투명 통과)

- [ ] **Step 4-5: 커밋**

```bash
git add orchestrator/app/graph/builder.py
git commit -m "feat(compliance): wire copy_compliance_gate into LangGraph (Phase 3)"
```

---

## Task 5: `test_marketing_graph_node_utilization.py` 업데이트

**Files:**
- Modify: `orchestrator/tests/test_marketing_graph_node_utilization.py`

이 테스트는 그래프의 모든 노드가 최소 1개 시나리오에서 실행됨을 보장한다. 새 노드 3개를 추가했으므로 업데이트가 필요하다.

- [ ] **Step 5-1: 현재 상태 확인 — 어떤 노드가 누락됐는지 확인**

```bash
PYTHONPATH=. .venv/bin/pytest \
    orchestrator/tests/test_marketing_graph_node_utilization.py::test_marketing_graph_node_utilization_matrix_covers_all_nodes \
    -v --tb=short
```

Expected: `FAILED` — `copy_compliance_gate`, `copy_compliance_interrupt`, `copy_compliance_resolution` 누락.

- [ ] **Step 5-2: `TRACEABLE_NODE_ATTRS`에 3개 추가**

`orchestrator/tests/test_marketing_graph_node_utilization.py`, `TRACEABLE_NODE_ATTRS` dict에 추가:

```python
TRACEABLE_NODE_ATTRS = {
    ...
    "no_copy_bypass": "no_copy_bypass_node",
    "copy_compliance_gate": "copy_compliance_gate_node",          # 추가
    "copy_compliance_interrupt": "copy_compliance_interrupt_node", # 추가
    "copy_compliance_resolution": "copy_compliance_resolution_node", # 추가
    "copy_spec_parser": "copy_spec_parser_node",
    ...
}
```

> `builder.py`가 이 함수들을 `copy_compliance_gate_node`, `copy_compliance_interrupt_node`, `copy_compliance_resolution_node` 이름으로 import했는지 확인한다.

- [ ] **Step 5-3: 기존 시나리오 includes 업데이트**

`NODE_UTILIZATION_MATRIX`에서 compliance gate를 거치는 시나리오에 `"copy_compliance_gate"` 추가:

```python
NODE_UTILIZATION_MATRIX = {
    ...
    "auto_pilot_text_overlay": {
        "includes": [
            "input", "validator", "format_planner", "tone_binding",
            "auto_pilot_copywriting",
            "copy_compliance_gate",   # 추가
            "copy_spec_parser",
            ...
        ],
        ...
    },
    "photo_suggest_candidates": {
        "includes": [
            "input", "product_preprocess",
            "copy_candidate_generation", "copy_candidate_selection_interrupt",
            "state_update_selected_copy",
            "copy_compliance_gate",   # 추가
            "t2i_request_builder", ...
        ],
        ...
    },
    "custom_copy_direct": {
        "includes": [
            "custom_copy_input", "custom_copy_validation",
            "copy_compliance_gate",   # 추가
            "copy_spec_parser", "text_renderer", "result"
        ],
        ...
    },
    "ocr_revision_loop": {
        "includes": [
            "background_ocr_gate", "ocr_image_revision", "final_ocr_gate",
            "ocr_layout_revision",
            # copy_compliance_gate는 이 시나리오도 거침
            "copy_compliance_gate",   # 추가
            "result"
        ],
        ...
    },
    ...
}
```

- [ ] **Step 5-4: 새 시나리오 matrix 항목 추가**

```python
NODE_UTILIZATION_MATRIX = {
    ...
    "compliance_blocked_and_resolved": {
        "includes": [
            "custom_copy_input",
            "custom_copy_validation",
            "copy_compliance_gate",
            "copy_compliance_interrupt",
            "copy_compliance_resolution",
            "copy_spec_parser",
            "result",
        ],
        "excludes": ["copy_candidate_generation", "auto_pilot_copywriting", "no_copy_bypass"],
    },
}
```

- [ ] **Step 5-5: 새 시나리오 함수 추가**

`orchestrator/tests/test_marketing_graph_node_utilization.py`, `_run_ocr_revision_loop` 함수 아래에:

```python
def _run_compliance_blocked_and_resolved(graph, trace: list[str]):
    """custom_copy_input에 blocked 카피 주입 → compliance interrupt → use_suggestion으로 해결."""
    def action():
        thread_id = "node-matrix-compliance-block"
        # user_custom_headline이 미리 설정돼 있으면 custom_copy_input이 interrupt 없이 통과한다.
        first = graph.invoke(
            {
                **_base_request(thread_id, copy_generation_mode="custom_input"),
                "context": {
                    "business_type": "beauty_skincare",
                    "item_or_service": "피부관리",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "user_custom_headline": "여드름 완치 보장",
            },
            config=_config(thread_id),
        )
        # compliance gate가 blocked → interrupt 발생
        assert first["__interrupt__"][0].value["type"] == "copy_compliance_review"
        # use_suggestion으로 재작성 → copy_spec_parser → result
        return graph.invoke(
            Command(resume={"action": "use_suggestion"}),
            config=_config(thread_id),
        )

    return _capture(trace, action)[0]
```

- [ ] **Step 5-6: `scenario_traces`에 새 시나리오 추가**

`test_marketing_graph_node_utilization_matrix_covers_all_nodes` 함수 안의 `scenario_traces` dict에:

```python
    scenario_traces = {
        ...
        "ocr_revision_loop": _run_ocr_revision_loop(graph, trace, monkeypatch),
        "compliance_blocked_and_resolved": _run_compliance_blocked_and_resolved(graph, trace),  # 추가
    }
```

- [ ] **Step 5-7: 통과 확인**

```bash
PYTHONPATH=. .venv/bin/pytest \
    orchestrator/tests/test_marketing_graph_node_utilization.py -v --tb=short
```

Expected: 전부 PASSED. 새 노드 3개가 커버됨.

- [ ] **Step 5-8: 커밋**

```bash
git add orchestrator/tests/test_marketing_graph_node_utilization.py
git commit -m "test(compliance): cover gate/interrupt/resolution nodes in utilization matrix"
```

---

## Task 6: 전체 회귀 테스트

- [ ] **Step 6-1: 전체 테스트 실행**

```bash
PYTHONPATH=. .venv/bin/pytest orchestrator/tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 기존 1121개 + 신규 약 25개 = 전부 PASSED, 0 FAILED.

- [ ] **Step 6-2: 최종 커밋**

```bash
git add -A
git commit -m "feat(compliance): Phase 3 complete — gate integrated into LangGraph"
```

---

## Phase 3 완료 체크리스트

- [ ] `copy_compliance_gate_node` 가 `marketing_copy`를 검사하고 결과를 `copy_compliance_gate` dict에 저장
- [ ] pass/warn → `copy_spec_parser` 직통 (기존 동작 보존)
- [ ] evidence_required/blocked → `copy_compliance_interrupt` → `copy_compliance_resolution`
- [ ] `use_suggestion` → `marketing_copy`가 `suggested_copy`로 교체, `copy_compliance_status = "rewritten_by_user_choice"`
- [ ] `keep_original_draft` / `submit_claim` → `copy_compliance_status = "manual_review_required"`, `publication_ready = False`
- [ ] `edit_manually` → `custom_copy_input`으로 루프백
- [ ] `cancel` → `END`
- [ ] `no_copy_bypass`는 gate를 거치지 않음 (카피 없음)
- [ ] 기존 e2e mock 테스트 전부 PASSED
- [ ] `test_marketing_graph_node_utilization.py` 전부 PASSED
- [ ] `original_copy`는 어떤 resolution에서도 삭제/덮어쓰지 않음

---

## 참고: Phase 3 엣지 변경 요약

```
변경 전:
  state_update_selected_copy → copy_spec_parser
  auto_pilot_copywriting     → copy_spec_parser
  custom_copy_validation     → copy_spec_parser

변경 후:
  state_update_selected_copy → copy_compliance_gate
  auto_pilot_copywriting     → copy_compliance_gate
  custom_copy_validation     → copy_compliance_gate
  copy_compliance_gate       → [pass/warn] copy_spec_parser
                             → [evidence_required/blocked] copy_compliance_interrupt
  copy_compliance_interrupt  → copy_compliance_resolution
  copy_compliance_resolution → [use_suggestion/submit_claim/keep_original] copy_spec_parser
                             → [edit_manually] custom_copy_input
                             → [cancel] END

유지:
  no_copy_bypass → copy_spec_parser  (카피 없음 → gate 불필요)
```
