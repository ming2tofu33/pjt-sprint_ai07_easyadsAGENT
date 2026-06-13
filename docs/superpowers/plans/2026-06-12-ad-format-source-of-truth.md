# ad_format Source of Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the `current_brief` vs `context` source-of-truth ambiguity (review priority ③) by giving `ad_format` — the one field with real divergence risk — a single canonical resolver and a single write-through setter, then documenting the state contract.

**Architecture:** Investigation (2026-06-12) showed the duplication problem concentrates on `ad_format`: it is stored in 5+ places (`current_brief["requested_ad_format"]`, `current_brief["ad_format"]`, `context.extra["ad_format"]`, top-level `selected_ad_format`, `context.extra["selected_ad_format"]`) and **each reader uses a different priority order** (format_planner: brief→extra; execution: top-level→brief→extra; chat.py: brief only). Other core fields (business_type, brand_tone, …) are already context-SoT — their brief copies are write-only UI mirrors that the frontend reads for display (`apps/web/lib/chat-thread-state-mapper.ts`), so the generic brief mirror writes stay. This plan adds `resolve_requested_ad_format()` (one canonical read order) and `set_requested_ad_format()` (one write-through point) in `state.py`, migrates all 7 read/write sites, and writes the contract doc.

**Tech Stack:** Python 3.12, LangGraph state dicts, pytest via `EASYADS_DB_BACKEND=memory uv run python -m pytest <path> -q` from repo root.

**Canonical priority (locked design):**
1. top-level `state["selected_ad_format"]` — explicit user selection this run
2. `current_brief["requested_ad_format"]` — user-confirmed/restored brief value
3. `context.extra["ad_format"]` — heuristic/LLM-inferred value
4. `current_brief["ad_format"]` — legacy generic-write key
5. `None` (callers supply their own default, e.g. format_planner's `"instagram_feed"`)

This matches the dominant existing orders; the only intentional behavior change is reference-template backfill (Task 4), which now backfills mirrors *consistently* instead of independently.

**Conventions:**
- Branch: create `refactor/ad-format-source-of-truth` stacked on `feat/orchestrator-auth-boundary`.
- All file/line references verified on that base today; line numbers are approximate, match the shown snippets.
- Conventional commits with the Co-Authored-By trailer shown in each commit step.

---

### Task 1: Resolver + write-through setter in state.py

**Files:**
- Modify: `orchestrator/app/graph/state.py` (add two functions directly below `update_current_brief`, ~line 450)
- Create: `orchestrator/tests/test_ad_format_source_of_truth.py`

- [ ] **Step 1: Write the failing tests**

Create `orchestrator/tests/test_ad_format_source_of_truth.py`:

```python
"""Tests for the canonical ad_format resolver and write-through setter."""

from orchestrator.app.graph.state import resolve_requested_ad_format, set_requested_ad_format


def _state(*, selected=None, brief=None, extra=None):
    state: dict = {"current_brief": dict(brief or {}), "context": {"extra": dict(extra or {})}}
    if selected is not None:
        state["selected_ad_format"] = selected
    return state


def test_returns_none_when_nothing_is_set():
    assert resolve_requested_ad_format(_state()) is None


def test_selected_ad_format_wins_over_everything():
    state = _state(
        selected="kakao_feed",
        brief={"requested_ad_format": "instagram_feed", "ad_format": "naver_blog"},
        extra={"ad_format": "instagram_story"},
    )
    assert resolve_requested_ad_format(state) == "kakao_feed"


def test_brief_requested_beats_context_extra():
    state = _state(brief={"requested_ad_format": "instagram_feed"}, extra={"ad_format": "instagram_story"})
    assert resolve_requested_ad_format(state) == "instagram_feed"


def test_context_extra_beats_legacy_brief_ad_format():
    state = _state(brief={"ad_format": "naver_blog"}, extra={"ad_format": "instagram_story"})
    assert resolve_requested_ad_format(state) == "instagram_story"


def test_legacy_brief_ad_format_is_last_resort():
    state = _state(brief={"ad_format": "naver_blog"})
    assert resolve_requested_ad_format(state) == "naver_blog"


def test_handles_missing_context_and_brief_keys():
    assert resolve_requested_ad_format({}) is None
    assert resolve_requested_ad_format({"context": None, "current_brief": None}) is None


def test_set_writes_both_mirrors():
    brief: dict = {}
    extra: dict = {}
    set_requested_ad_format(brief, extra, "instagram_feed")
    assert brief["requested_ad_format"] == "instagram_feed"
    assert extra["ad_format"] == "instagram_feed"


def test_set_overwrites_divergent_mirrors():
    brief = {"requested_ad_format": "naver_blog"}
    extra = {"ad_format": "instagram_story"}
    set_requested_ad_format(brief, extra, "kakao_feed")
    assert brief["requested_ad_format"] == "kakao_feed"
    assert extra["ad_format"] == "kakao_feed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_ad_format_source_of_truth.py -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_requested_ad_format'`.

- [ ] **Step 3: Implement the helpers**

In `orchestrator/app/graph/state.py`, add directly below `update_current_brief` (which ends around line 450):

```python
def resolve_requested_ad_format(state: dict[str, Any] | MarketingState) -> str | None:
    """Canonical ad_format read order — the single source-of-truth resolver.

    ad_format historically lived in several mirrors with per-reader priority
    orders. All business-logic reads must go through this function:
      1. top-level selected_ad_format (explicit user selection)
      2. current_brief.requested_ad_format (confirmed/restored brief)
      3. context.extra.ad_format (heuristic/LLM inference)
      4. current_brief.ad_format (legacy generic-write key)
    Returns None when unset; callers own their defaults.
    """
    brief = state.get("current_brief") or {}
    context = state.get("context") or {}
    extra = (context.get("extra") if isinstance(context, dict) else getattr(context, "extra", None)) or {}
    for candidate in (
        state.get("selected_ad_format"),
        brief.get("requested_ad_format"),
        extra.get("ad_format"),
        brief.get("ad_format"),
    ):
        if candidate:
            return str(candidate)
    return None


def set_requested_ad_format(current_brief: dict[str, Any], context_extra: dict[str, Any], value: str) -> None:
    """Write-through setter: keep the two ad_format mirrors consistent.

    current_brief.requested_ad_format is the UI read-model copy;
    context.extra.ad_format is the business-context copy. Writing them
    anywhere else by hand is how they diverged — always use this.
    """
    current_brief["requested_ad_format"] = value
    context_extra["ad_format"] = value
```

Note: `context` may be a dict or a `MarketingContext` model depending on the caller — the resolver handles both (`getattr(context, "extra", None)`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_ad_format_source_of_truth.py orchestrator/tests/test_langgraph_state.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_ad_format_source_of_truth.py
git commit -m "feat(graph): add canonical ad_format resolver and write-through setter

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Migrate the readers

Four read sites get the resolver. Per-call inputs that outrank state (e.g. `request.ad_format`) stay local to their call sites.

**Files:**
- Modify: `orchestrator/app/llm/nodes/format_planner.py:35-49` (`resolve_ad_format`)
- Modify: `orchestrator/app/graph/nodes.py:63` (validator_node)
- Modify: `orchestrator/app/generation_jobs/execution.py:77-83`
- Modify: `orchestrator/app/api/chat.py:406-412`

- [ ] **Step 1: format_planner.resolve_ad_format**

Current code:

```python
def resolve_ad_format(state: MarketingState) -> str:
    current_brief = state.get("current_brief", {})
    context = context_to_model(state.get("context"))
    validator_output = state.get("validator_output") or {}
    candidates = [
        current_brief.get("requested_ad_format"),
        context.extra.get("ad_format"),
        _extract_validator_ad_format(validator_output),
        current_brief.get("ad_format"),
        "instagram_feed",
    ]
    for candidate in candidates:
        if candidate in VALID_AD_FORMATS:
            return str(candidate)
    return "instagram_feed"
```

Replace with:

```python
def resolve_ad_format(state: MarketingState) -> str:
    validator_output = state.get("validator_output") or {}
    candidates = [
        resolve_requested_ad_format(state),
        _extract_validator_ad_format(validator_output),
        "instagram_feed",
    ]
    for candidate in candidates:
        if candidate in VALID_AD_FORMATS:
            return str(candidate)
    return "instagram_feed"
```

Add to the file's imports: `from orchestrator.app.graph.state import resolve_requested_ad_format` (the file already imports from `orchestrator.app.graph.state`; extend that import line). If `context_to_model` becomes unused in this file after the change, remove it from the import; if it is still used elsewhere in the file, leave it.

Behavior note (intentional, document in commit body if asked): the legacy `current_brief["ad_format"]` key now ranks above the validator fallback instead of below it. In practice both are written together by the state_update generic mirror, so they cannot disagree in current flows; the resolver order is the contract going forward.

- [ ] **Step 2: validator_node in graph/nodes.py**

Current line 63:

```python
    requested_ad_format = state.get("current_brief", {}).get("requested_ad_format") or infer_ad_format(text) or extra.get("ad_format")
```

Replace with:

```python
    requested_ad_format = resolve_requested_ad_format(state) or infer_ad_format(text)
```

(Equivalence argument: the resolver covers `current_brief["requested_ad_format"]` and the state's `context.extra["ad_format"]`. The original third term read the LOCAL `extra` dict, which can additionally contain a value set a few lines above by `extra["ad_format"] = infer_ad_format(text)` — but that value is exactly `infer_ad_format(text)`, which the second term already recomputes deterministically. So the two expressions return identical results.)

Extend the existing `from orchestrator.app.graph.state import (...)` import block in `orchestrator/app/graph/nodes.py` with `resolve_requested_ad_format` and `set_requested_ad_format` (the setter is used in Task 3).

- [ ] **Step 3: execution.py read**

Current lines 77-83:

```python
    selected_ad_format = _canonical_ad_format(
        request.ad_format
        or selected_channel_id
        or state.get("selected_ad_format")
        or current_brief.get("requested_ad_format")
        or context_extra.get("ad_format")
    )
```

Replace with:

```python
    selected_ad_format = _canonical_ad_format(
        request.ad_format
        or selected_channel_id
        or resolve_requested_ad_format(state)
    )
```

Add the import near the function's other imports: `from orchestrator.app.graph.state import resolve_requested_ad_format, set_requested_ad_format` (setter used in Task 3; place it as a module-level import alongside existing ones, or extend an existing `orchestrator.app.graph.state` import if present).

- [ ] **Step 4: chat.py read**

Current line 411:

```python
            selected_channel_id=_selected_channel_id_for_ad_format(current_brief.get("requested_ad_format")),
```

Replace with:

```python
            selected_channel_id=_selected_channel_id_for_ad_format(resolve_requested_ad_format(result)),
```

(`result` is the graph result dict with the same state shape.) If `current_brief` (line 406) becomes unused in that function after this change, delete the now-dead `current_brief = result.get("current_brief") or {}` line; if other lines in the same function still use it, keep it. Add `from orchestrator.app.graph.state import resolve_requested_ad_format` to chat.py's imports.

- [ ] **Step 5: Run the affected suites**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "format_planner or ad_format or intake or chat_api or generation_job_graph" -q`
Expected: PASS, zero failures. If a test fails, compare against the branch base (`git stash`) before assuming regression.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/llm/nodes/format_planner.py orchestrator/app/graph/nodes.py orchestrator/app/generation_jobs/execution.py orchestrator/app/api/chat.py
git commit -m "refactor(graph): route all ad_format reads through canonical resolver

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Migrate the writers

Three sites hand-write the mirror pair; all switch to `set_requested_ad_format`. Top-level `selected_ad_format` / `extra["selected_ad_format"]` writes are separate concerns and stay as-is.

**Files:**
- Modify: `orchestrator/app/graph/nodes.py:242-246` (state_update ad_format branch)
- Modify: `orchestrator/app/generation_jobs/execution.py:90-94`
- Modify: `orchestrator/app/llm/nodes/copy_candidates.py:529-533`

- [ ] **Step 1: state_update ad_format branch in graph/nodes.py**

Current code:

```python
    elif field == "ad_format":
        extra["ad_format"] = value
        context_data["extra"] = extra
        update_current_brief(state, {"requested_ad_format": value})
        updated = True
```

Replace with:

```python
    elif field == "ad_format":
        set_requested_ad_format(state.setdefault("current_brief", {}), extra, value)
        context_data["extra"] = extra
        updated = True
```

(`update_current_brief`'s `updated_at` bump still happens via the unconditional `update_current_brief(state, {field: value})` call a few lines below, so dropping the explicit call here changes nothing observable.)

- [ ] **Step 2: execution.py write block**

Current code:

```python
    if selected_ad_format:
        state["selected_ad_format"] = selected_ad_format
        current_brief["requested_ad_format"] = selected_ad_format
        context_extra["ad_format"] = selected_ad_format
        context_extra["selected_ad_format"] = selected_ad_format
```

Replace with:

```python
    if selected_ad_format:
        state["selected_ad_format"] = selected_ad_format
        set_requested_ad_format(current_brief, context_extra, selected_ad_format)
        context_extra["selected_ad_format"] = selected_ad_format
```

- [ ] **Step 3: copy_candidates.py write block**

Current code:

```python
    if selected_ad_format:
        update["selected_ad_format"] = selected_ad_format
        current_brief["requested_ad_format"] = selected_ad_format
        context_extra["ad_format"] = selected_ad_format
        context_extra["selected_ad_format"] = selected_ad_format
```

Replace with:

```python
    if selected_ad_format:
        update["selected_ad_format"] = selected_ad_format
        set_requested_ad_format(current_brief, context_extra, selected_ad_format)
        context_extra["selected_ad_format"] = selected_ad_format
```

Add to copy_candidates.py's existing `from orchestrator.app.graph.state import ...` import: `set_requested_ad_format`.

- [ ] **Step 4: Verify no hand-written mirror pairs remain**

Run: `grep -rn 'current_brief\["requested_ad_format"\]\s*=' orchestrator/app --include="*.py"`
Expected: only `orchestrator/app/graph/state.py` (inside `set_requested_ad_format`) and `orchestrator/app/reference_catalog/nodes.py` (migrated in Task 4). Anything else is a missed site — migrate it the same way and report it.

- [ ] **Step 5: Run the affected suites**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "copy or generation_job or state_update or langgraph" -q`
Expected: PASS, zero failures.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/graph/nodes.py orchestrator/app/generation_jobs/execution.py orchestrator/app/llm/nodes/copy_candidates.py
git commit -m "refactor(graph): route all ad_format writes through write-through setter

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Consistent reference-template backfill

The reference-template node fills each mirror **independently** — if exactly one mirror already has a value, the other gets the template default, creating divergence. This is the one intentional behavior change: backfill from the existing canonical value first.

**Files:**
- Modify: `orchestrator/app/reference_catalog/nodes.py:100-113`
- Test: `orchestrator/tests/test_ad_format_source_of_truth.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `orchestrator/tests/test_ad_format_source_of_truth.py`:

```python
def test_backfill_prefers_existing_value_over_template_default():
    from orchestrator.app.graph.state import backfill_requested_ad_format

    # brief already confirmed instagram_feed; extra is empty; template says naver_blog.
    brief = {"requested_ad_format": "instagram_feed"}
    extra: dict = {}
    backfill_requested_ad_format(brief, extra, "naver_blog")
    assert brief["requested_ad_format"] == "instagram_feed"
    assert extra["ad_format"] == "instagram_feed"  # backfilled from brief, NOT the template


def test_backfill_uses_template_when_both_missing():
    from orchestrator.app.graph.state import backfill_requested_ad_format

    brief: dict = {}
    extra: dict = {}
    backfill_requested_ad_format(brief, extra, "naver_blog")
    assert brief["requested_ad_format"] == "naver_blog"
    assert extra["ad_format"] == "naver_blog"


def test_backfill_noop_when_no_value_available():
    from orchestrator.app.graph.state import backfill_requested_ad_format

    brief: dict = {}
    extra: dict = {}
    backfill_requested_ad_format(brief, extra, None)
    assert brief == {}
    assert extra == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_ad_format_source_of_truth.py -q`
Expected: the 3 new tests FAIL with `ImportError: cannot import name 'backfill_requested_ad_format'`; the 8 Task-1 tests pass.

- [ ] **Step 3: Implement the backfill helper**

In `orchestrator/app/graph/state.py`, add directly below `set_requested_ad_format`:

```python
def backfill_requested_ad_format(
    current_brief: dict[str, Any], context_extra: dict[str, Any], default: str | None
) -> None:
    """Fill missing ad_format mirrors without overwriting an existing choice.

    Priority: an already-set mirror value wins over the supplied default
    (e.g. a reference template's ad_format). Ensures both mirrors end up
    identical — the legacy code filled each independently and could diverge.
    """
    value = current_brief.get("requested_ad_format") or context_extra.get("ad_format") or default
    if not value:
        return
    current_brief.setdefault("requested_ad_format", value)
    context_extra.setdefault("ad_format", value)
```

- [ ] **Step 4: Migrate the reference-template node**

In `orchestrator/app/reference_catalog/nodes.py`, current code (two separate fills, lines ~100-101 and ~112-113):

```python
    template_ad_format = context_defaults.get("ad_format")
    if template_ad_format and not extra.get("ad_format"):
        extra["ad_format"] = template_ad_format
```

and, ~11 lines below:

```python
    if template_ad_format and not current_brief.get("requested_ad_format"):
        current_brief["requested_ad_format"] = template_ad_format
```

Replace the FIRST snippet with:

```python
    template_ad_format = context_defaults.get("ad_format")
    backfill_requested_ad_format(current_brief, extra, template_ad_format)
```

and DELETE the second snippet entirely (the helper already handled the brief side). Add the import: `from orchestrator.app.graph.state import backfill_requested_ad_format` (extend the file's existing imports). Note: `current_brief` must already be in scope at the first snippet's location — it is (the function builds it above); verify before editing.

- [ ] **Step 5: Run tests to verify they pass**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_ad_format_source_of_truth.py orchestrator/tests -k "reference" -q`
Expected: PASS (all 11 tests in the new file + all reference-catalog tests).

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/graph/state.py orchestrator/app/reference_catalog/nodes.py orchestrator/tests/test_ad_format_source_of_truth.py
git commit -m "fix(reference): backfill ad_format mirrors consistently from existing value

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: State source-of-truth contract doc

**Files:**
- Create: `docs/state-source-of-truth.md`

- [ ] **Step 1: Write the doc**

Create `docs/state-source-of-truth.md`:

````markdown
# MarketingState Source of Truth 계약

코드 리뷰 지적 사항 "current_brief와 context가 같은 값을 중복 관리하고
어느 쪽이 SoT인지 불분명하다"에 대한 확정 계약. (2026-06-12)

## 역할 정의

| 저장소 | 역할 | 읽기 주체 |
|---|---|---|
| `context` (MarketingContext) | 비즈니스 필드의 SoT — business_type, brand_tone, usp 등 12개 코어 필드 + `extra` | 비즈니스 로직 (LLM 노드, 플래너) |
| `current_brief` | **UI read model** — 프론트엔드 표시용 미러 + UI 전용 키 (cached_options, selected_tone, copy_generation_mode_confirmed, reference_template_* 등) | 프론트엔드 (`chat-thread-state-mapper.ts`), 스냅샷 |
| top-level state 필드 | 그래프 실행 플래그/선택값 — copy_generation_mode, selected_ad_format 등 | 그래프 라우팅 |

## 규칙

1. **비즈니스 로직은 current_brief를 직접 읽지 않는다.** 코어 필드는
   `context`에서, ad_format은 `resolve_requested_ad_format(state)`로 읽는다.
2. **brief 미러 쓰기는 write-through 헬퍼로만 한다.** ad_format은
   `set_requested_ad_format` / `backfill_requested_ad_format`
   (`orchestrator/app/graph/state.py`). 손으로 두 미러를 쓰는 코드는 버그다.
3. `state_update_node`의 제네릭 미러 쓰기(`update_current_brief(state,
   {field: value})`)는 FE 표시용으로 유지한다 — 단, 그 값을 다시 읽는
   비즈니스 로직을 추가하지 말 것.

## ad_format의 canonical 우선순위

`resolve_requested_ad_format()` 내부 순서이자 유일한 계약:

1. `state["selected_ad_format"]` — 이번 실행에서의 명시적 사용자 선택
2. `current_brief["requested_ad_format"]` — 확정/복원된 브리프 값
3. `context.extra["ad_format"]` — 휴리스틱/LLM 추론값
4. `current_brief["ad_format"]` — 레거시 제네릭 키
5. `None` — 기본값은 호출자 소관 (format_planner는 `"instagram_feed"`)

이전에는 reader 4곳이 각자 다른 순서를 썼다 (format_planner: 1을 안 봄,
execution: 2·3 순서 동일하지만 별도 구현, chat.py: 2만 봄). 미러가
갈라지면 reader마다 다른 광고 형식으로 동작하는 버그였다.

## copy_generation_mode

SoT는 **top-level `state["copy_generation_mode"]`**. brief의 사본은
FE 표시용 write-only 미러이고, `copy_generation_mode_confirmed`는
brief 전용 키(중복 아님)다.

## 다음 단계 (리뷰 우선순위 ④와의 연결)

이 문서의 규칙은 MarketingState dict|Model union 정리(④)의 전제다.
④ 진행 시 brief 전용 키들을 TypedDict로 명세하는 것부터 시작할 것.
````

- [ ] **Step 2: Commit**

```bash
git add docs/state-source-of-truth.md
git commit -m "docs: lock current_brief vs context source-of-truth contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Full orchestrator suite**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -q`
Expected: PASS — branch base was 1326 passed / 2 skipped; expect that plus the 11 new tests, zero new failures.

- [ ] **Step 2: Grep audit — no business-logic brief reads of ad_format remain**

Run: `grep -rnE 'current_brief[^=]*\.get\("(requested_)?ad_format"\)|current_brief\["(requested_)?ad_format"\]' orchestrator/app --include="*.py"`
Expected: matches only inside `orchestrator/app/graph/state.py` (the resolver/setter/backfill bodies). Any other match is a missed migration.

- [ ] **Step 3: Confirm clean tree**

Run: `git status --short`
Expected: empty output.
