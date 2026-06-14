# MarketingState Union Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad-hoc `Model(**(state.get("field") or {}))` coercions scattered across nodes with a single generic typed reader `read_model(state, key, Model)`, normalize the migrated `dict | Model | None` annotations to `dict | None`, and document the "state stores dicts, nodes parse on read" convention (review priority ④, "convention + generic helper" scope).

**Architecture:** Investigation (2026-06-14) found exactly one established helper (`context_to_model`) and ~24 ad-hoc model-construction sites across 13 node files, all of the same shape: a state field stored as a serialized dict gets re-parsed into a Pydantic model at point of use. This plan adds `read_model` (a generalization of `context_to_model`), makes `context_to_model` delegate to it for backward compatibility, migrates all ad-hoc sites batch-by-batch, then normalizes the type annotations of the migrated fields so the TypedDict reflects the real stored form (dict). The canonical stored form stays dict (required for LangGraph Postgres checkpointer serialization); models are a read-time view only.

**Tech Stack:** Python 3.12, Pydantic 2, LangGraph TypedDict state, pytest via `EASYADS_DB_BACKEND=memory uv run python -m pytest <path> -q` from repo root.

**Scope boundaries (locked):**
- IN: generic `read_model` helper; migrate the ~24 `Model(**(state.get(...)))` sites; normalize annotations for the migrated model-backed fields; convention doc.
- OUT: sub-state splitting of MarketingState (separate future effort); the ~40 plain `dict | None` fields that have no model (nothing to normalize); write-side changes (writes already `.model_dump()`; `read_model` tolerates either form defensively).

**Conventions:**
- Branch `refactor/marketing-state-union-cleanup` is already created off latest `origin/develop` (includes ad_format SoT from merged PR #157).
- Line numbers below were verified on this base today; they are approximate — match the shown code snippets, not the line numbers.
- An untracked file `docs/superpowers/plans/2026-06-13-generation-job-background-resume-reliability.md` exists in the tree from another effort — do NOT stage or modify it.
- Conventional commits with the Co-Authored-By trailer shown in each commit step.

---

### Task 1: Generic `read_model` helper + delegate `context_to_model`

**Files:**
- Modify: `orchestrator/app/graph/state.py` (add `read_model` above `context_to_model` ~line 241; refactor `context_to_model` body)
- Create: `orchestrator/tests/test_read_model_helper.py`

- [ ] **Step 1: Write the failing tests**

Create `orchestrator/tests/test_read_model_helper.py`:

```python
"""Tests for the generic state model reader."""

from orchestrator.app.graph.state import context_to_model, read_model
from orchestrator.app.schemas.llm_marketing import CopySpec, MarketingContext


def test_read_model_parses_dict_to_model():
    state = {"copy_spec": {"headline": "봄 신메뉴"}}
    spec = read_model(state, "copy_spec", CopySpec)
    assert isinstance(spec, CopySpec)
    assert spec.headline == "봄 신메뉴"


def test_read_model_returns_existing_model_instance_untouched():
    existing = CopySpec(headline="이미 모델")
    state = {"copy_spec": existing}
    assert read_model(state, "copy_spec", CopySpec) is existing


def test_read_model_missing_key_returns_empty_model():
    spec = read_model({}, "copy_spec", CopySpec)
    assert isinstance(spec, CopySpec)


def test_read_model_none_value_returns_empty_model():
    spec = read_model({"copy_spec": None}, "copy_spec", CopySpec)
    assert isinstance(spec, CopySpec)


def test_read_model_default_none_returns_none_when_absent():
    assert read_model({}, "copy_spec", CopySpec, default=None) is None
    assert read_model({"copy_spec": None}, "copy_spec", CopySpec, default=None) is None


def test_read_model_default_none_still_parses_present_dict():
    spec = read_model({"copy_spec": {"headline": "x"}}, "copy_spec", CopySpec, default=None)
    assert isinstance(spec, CopySpec)
    assert spec.headline == "x"


def test_context_to_model_still_works_after_delegation():
    # Backward-compat: existing helper keeps its exact behavior.
    assert isinstance(context_to_model(None), MarketingContext)
    assert isinstance(context_to_model({"business_type": "cafe"}), MarketingContext)
    existing = MarketingContext(business_type="cafe")
    assert context_to_model(existing) is existing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_read_model_helper.py -q`
Expected: FAIL — `ImportError: cannot import name 'read_model'`.

- [ ] **Step 3: Implement `read_model` and delegate `context_to_model`**

In `orchestrator/app/graph/state.py`, add `from typing import TypeVar` to the typing import (it currently imports `Any, NotRequired, TypedDict`), and near the top-level (just above the existing `context_to_model`, ~line 241) add exactly this. The `_UNSET` sentinel lets the body distinguish "default omitted" (→ empty model) from "`default=None` passed explicitly" (→ `None`):

```python
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_UNSET = object()


def read_model(
    state: dict[str, Any],
    key: str,
    model_cls: type[_ModelT],
    *,
    default: Any = _UNSET,
) -> _ModelT | None:
    """Read a state field as a Pydantic model — the one coercion entry point.

    State fields are stored as serialized dicts (LangGraph checkpointer needs
    JSON-able state); nodes parse to a model at point of use. This replaces
    ad-hoc `Model(**(state.get(key) or {}))` so the dict|model duality lives
    in exactly one place.

    - Existing model instance is returned untouched (idempotent).
    - Missing/None value: returns an empty `model_cls()` by default, or `None`
      if `default=None` was passed explicitly.
    """
    value = state.get(key)
    if isinstance(value, model_cls):
        return value
    if not value:
        return None if default is None else model_cls()
    return model_cls(**value)
```

Then refactor `context_to_model` to delegate:

```python
def context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    return MarketingContext(**(context or {}))
```

becomes:

```python
def context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    return read_model({"context": context}, "context", MarketingContext)
```

(Behavior identical: present dict → parsed; None/empty → empty `MarketingContext()`; existing model → returned as-is.)

Verify `BaseModel` is imported in state.py; if not, add `from pydantic import BaseModel`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_read_model_helper.py orchestrator/tests/test_langgraph_state.py -q`
Expected: PASS (all — including the existing state tests that exercise `context_to_model`).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_read_model_helper.py
git commit -m "feat(graph): add generic read_model helper; context_to_model delegates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Migrate the high-frequency spec reads (copy_spec / text_layout_spec / text_style_spec)

These three models account for most ad-hoc sites. All follow `Model(**(state.get("field") or {}))`.

**Files:**
- Modify: `orchestrator/app/llm/nodes/text_layout_planner.py` (copy_spec, text_style_spec)
- Modify: `orchestrator/app/llm/nodes/text_renderer.py` (copy_spec)
- Modify: `orchestrator/app/llm/nodes/post_t2i_layout_refiner.py` (copy_spec, text_style_spec, text_layout_spec ×3)
- Modify: `orchestrator/app/llm/nodes/readability_gate.py` (text_layout_spec)
- Modify: `orchestrator/app/llm/nodes/adaptive_typography_refiner.py` (text_layout_spec, text_style_spec)
- Modify: `orchestrator/app/llm/nodes/image_prompt_planner.py` (text_layout_spec ×2)

- [ ] **Step 1: Establish characterization coverage exists**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "text_layout or text_render or readability or typography or image_prompt or post_t2i or layout_planner" -q`
Expected: PASS (record the count). These are the regression guard for this task — the migration must keep them green.

- [ ] **Step 2: Migrate each site**

In every file above, replace the pattern (shown for each variable). The replacement is mechanical: `CopySpec(**(state.get("copy_spec") or {}))` → `read_model(state, "copy_spec", CopySpec)`, and likewise for `text_style_spec`/`TextStyleSpec` and `text_layout_spec`/`TextLayoutSpec`.

Concrete edits:

- `text_layout_planner.py`:
  - `CopySpec(**(state.get("copy_spec") or {}))` → `read_model(state, "copy_spec", CopySpec)`
  - `TextStyleSpec(**(state.get("text_style_spec") or {}))` → `read_model(state, "text_style_spec", TextStyleSpec)`
- `text_renderer.py`:
  - `CopySpec(**(state.get("copy_spec") or {}))` → `read_model(state, "copy_spec", CopySpec)`
- `readability_gate.py`:
  - `TextLayoutSpec(**(state.get("text_layout_spec") or {}))` → `read_model(state, "text_layout_spec", TextLayoutSpec)`
- `adaptive_typography_refiner.py`:
  - `TextLayoutSpec(**(state.get("text_layout_spec") or {}))` → `read_model(state, "text_layout_spec", TextLayoutSpec)`
  - `TextStyleSpec(**(state.get("text_style_spec") or {}))` → `read_model(state, "text_style_spec", TextStyleSpec)`
- `image_prompt_planner.py` (two occurrences, replace both):
  - `TextLayoutSpec(**(state.get("text_layout_spec") or {}))` → `read_model(state, "text_layout_spec", TextLayoutSpec)`
- `post_t2i_layout_refiner.py`:
  - `CopySpec(**(state.get("copy_spec") or {}))` → `read_model(state, "copy_spec", CopySpec)`
  - `TextStyleSpec(**(state.get("text_style_spec") or {}))` → `read_model(state, "text_style_spec", TextStyleSpec)`
  - The first three `TextLayoutSpec(**(state.get("text_layout_spec") or {}))` → `read_model(state, "text_layout_spec", TextLayoutSpec)`
  - The conditional form `TextLayoutSpec(**x) if state.get("text_layout_spec") else None` → `read_model(state, "text_layout_spec", TextLayoutSpec, default=None)` (preserves the `else None` semantics)

In each file, add `read_model` to the existing `from orchestrator.app.graph.state import ...` import (every one of these files already imports from that module — extend the import list; do not add a second import line). The model classes (`CopySpec`, etc.) remain imported since they are passed as arguments.

- [ ] **Step 3: Audit — no spec ad-hoc coercion remains in these files**

Run: `grep -rnE "(CopySpec|TextStyleSpec|TextLayoutSpec)\(\*\*" orchestrator/app/llm/nodes/text_layout_planner.py orchestrator/app/llm/nodes/text_renderer.py orchestrator/app/llm/nodes/post_t2i_layout_refiner.py orchestrator/app/llm/nodes/readability_gate.py orchestrator/app/llm/nodes/adaptive_typography_refiner.py orchestrator/app/llm/nodes/image_prompt_planner.py`
Expected: no output.

- [ ] **Step 4: Run the regression guard**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "text_layout or text_render or readability or typography or image_prompt or post_t2i or layout_planner" -q`
Expected: PASS — same count as Step 1, zero failures.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/llm/nodes/text_layout_planner.py orchestrator/app/llm/nodes/text_renderer.py orchestrator/app/llm/nodes/post_t2i_layout_refiner.py orchestrator/app/llm/nodes/readability_gate.py orchestrator/app/llm/nodes/adaptive_typography_refiner.py orchestrator/app/llm/nodes/image_prompt_planner.py
git commit -m "refactor(llm): read copy/layout/style specs via read_model helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Migrate the remaining model reads

The leftover ad-hoc sites: `marketing_copy` (MarketingCopy), `t2i_request` (T2IRequest), `image_prompt` (ImagePrompt), plus the `isinstance(...) else Model(**...)` form in `prompt_renderer.py` for `image_prompt_spec` (ImagePromptSpec).

**Files:**
- Modify: `orchestrator/app/llm/nodes/copy_spec_parser.py` (marketing_copy)
- Modify: `orchestrator/app/llm/nodes/t2i_generation.py` (t2i_request)
- Modify: `orchestrator/app/llm/nodes/prompt_renderer.py` (image_prompt)
- Modify: `orchestrator/app/llm/prompt_renderer.py` (image_prompt_spec — isinstance form)

- [ ] **Step 1: Migrate the plain `state.get` forms**

- `copy_spec_parser.py`: `MarketingCopy(**(state.get("marketing_copy") or {}))` → `read_model(state, "marketing_copy", MarketingCopy)`
- `t2i_generation.py`: `T2IRequest(**(state.get("t2i_request") or {}))` → `read_model(state, "t2i_request", T2IRequest)`
- `prompt_renderer.py` (node, `orchestrator/app/llm/nodes/prompt_renderer.py`): `ImagePrompt(**(state.get("image_prompt") or {}))` → `read_model(state, "image_prompt", ImagePrompt)`

Add `read_model` to each file's existing `orchestrator.app.graph.state` import. Note: `copy_spec_parser.py` also has a `... state.get("selected_reference_template")).model_dump()` site — that one is NOT a model-read of a model-backed field (it dumps a template into a dict); leave it unchanged.

- [ ] **Step 2: Migrate the `isinstance` form in the prompt_renderer library**

In `orchestrator/app/llm/prompt_renderer.py`, current code:

```python
    spec = image_prompt_spec if isinstance(image_prompt_spec, ImagePromptSpec) else ImagePromptSpec(**image_prompt_spec)
```

This reads a local variable `image_prompt_spec`, not `state[...]`. `read_model` keys off a dict, so wrap it:

```python
    spec = read_model({"image_prompt_spec": image_prompt_spec}, "image_prompt_spec", ImagePromptSpec)
```

Behavior note: the original would raise if `image_prompt_spec` were `None` (TypeError on `**None`); `read_model` instead returns an empty `ImagePromptSpec()`. If existing callers guarantee non-None, this is equivalent for valid inputs and strictly more robust. Add `read_model` to this file's `orchestrator.app.graph.state` import (add the import if the file does not already import from that module — verify first; if importing would create a circular import, STOP and report rather than forcing it).

- [ ] **Step 3: Audit remaining ad-hoc model coercions repo-wide**

Run: `grep -rnE "(MarketingCopy|T2IRequest|ImagePrompt|ImagePromptSpec)\(\*\*" orchestrator/app --include="*.py"`
Expected: no output (all migrated). If any remain, migrate them the same way and report.

- [ ] **Step 4: Run the regression guard**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "copy_spec or t2i or prompt_render or image_prompt" -q`
Expected: PASS, zero failures.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/llm/nodes/copy_spec_parser.py orchestrator/app/llm/nodes/t2i_generation.py orchestrator/app/llm/nodes/prompt_renderer.py orchestrator/app/llm/prompt_renderer.py
git commit -m "refactor(llm): read remaining model fields via read_model helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Normalize migrated field annotations to `dict | None`

Now that reads of these fields go through `read_model`, the TypedDict should reflect the real stored form (dict). Change the migrated model-backed fields from `dict[str, Any] | Model | None` to `dict[str, Any] | None`. `context` stays `dict | MarketingContext` (it has a non-None default and is read everywhere via `context_to_model`; leave it to avoid churn — out of scope).

**Files:**
- Modify: `orchestrator/app/graph/state.py` (the MarketingState field annotations)

- [ ] **Step 1: Normalize the annotations of the migrated fields only**

In the `MarketingState` TypedDict, change these exact lines (the fields migrated in Tasks 2-3):

```python
    marketing_copy: dict[str, Any] | MarketingCopy | None
    copy_spec: dict[str, Any] | CopySpec | None
    text_layout_spec: dict[str, Any] | TextLayoutSpec | None
    text_style_spec: dict[str, Any] | TextStyleSpec | None
    image_prompt_spec: dict[str, Any] | ImagePromptSpec | None
    image_prompt: dict[str, Any] | ImagePrompt | None
    t2i_request: dict[str, Any] | T2IRequest | None
```

to:

```python
    marketing_copy: dict[str, Any] | None
    copy_spec: dict[str, Any] | None
    text_layout_spec: dict[str, Any] | None
    text_style_spec: dict[str, Any] | None
    image_prompt_spec: dict[str, Any] | None
    image_prompt: dict[str, Any] | None
    t2i_request: dict[str, Any] | None
```

Leave every other field untouched (the remaining `dict | Model | None` fields whose reads were not migrated in this pass keep their annotation — normalizing them without migrating their reads would be misleading).

- [ ] **Step 2: Confirm the model imports are still needed**

Run: `grep -nE "\b(MarketingCopy|CopySpec|TextLayoutSpec|TextStyleSpec|ImagePromptSpec|ImagePrompt|T2IRequest)\b" orchestrator/app/graph/state.py`
Expected: each model name no longer appears (the annotations were their only use in state.py). If a name still appears elsewhere in state.py, keep its import; otherwise remove now-unused names from the `from orchestrator.app.schemas.llm_marketing import (...)` block. Remove only the names that have zero remaining references in the file.

- [ ] **Step 3: Static sanity — import the module**

Run: `EASYADS_DB_BACKEND=memory uv run python -c "import orchestrator.app.graph.state; print('import ok')"`
Expected: `import ok` (no NameError from a removed-but-still-referenced import).

- [ ] **Step 4: Run state + node suites**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -k "langgraph or state or copy or layout or t2i or image_prompt" -q`
Expected: PASS, zero failures.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/graph/state.py
git commit -m "refactor(graph): normalize migrated field annotations to dict form

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Convention doc

**Files:**
- Modify: `docs/state-source-of-truth.md` (append a section)

- [ ] **Step 1: Append the convention section**

Append to `docs/state-source-of-truth.md`:

```markdown
## dict ↔ Pydantic 모델 경계 (read_model 컨벤션)

리뷰 지적 ④ "필드가 dict|Model 유니온이라 직렬화 dict인지 모델인지
모른다"에 대한 확정 규칙. (2026-06-14)

### 규칙

1. **저장 형태는 항상 dict.** LangGraph Postgres checkpointer가 state를
   JSON 직렬화해야 하므로, MarketingState 필드의 canonical 형태는
   `.model_dump()`된 dict다. 노드가 반환할 때 `.model_dump()`로 저장한다.
2. **읽을 때만 모델로 파싱한다.** 노드 안에서 모델이 필요하면
   `read_model(state, "field", Model)` 단일 헬퍼로 읽는다. 직접
   `Model(**(state.get("field") or {}))`를 쓰지 않는다 — 그 이중성을
   한 곳(`read_model`)에 가둔 게 이 작업의 핵심이다.
3. `read_model`은 방어적이다: 이미 모델이면 그대로 반환, 없으면
   빈 모델(또는 `default=None` 시 `None`)을 돌려준다.
4. 따라서 model-backed 필드의 타입 주석은 `dict[str, Any] | None`이다
   (`| Model`을 빼서 "저장 형태는 dict"임을 타입으로 표현).

### 적용 범위

이번 패스에서 마이그레이션한 필드: `marketing_copy`, `copy_spec`,
`text_layout_spec`, `text_style_spec`, `image_prompt_spec`,
`image_prompt`, `t2i_request`. `context`는 기존 `context_to_model`
경로를 유지한다(읽기 빈도가 높고 non-None 기본값이라 별도).

아직 `dict | Model | None`로 남은 필드들(validator_output, ad_format_spec,
layout_spec 등)은 reader 마이그레이션이 안 된 것이므로 주석을 먼저 바꾸지
말 것 — read_model로 읽도록 바꾼 뒤 주석을 정규화한다.
```

- [ ] **Step 2: Commit**

```bash
git add docs/state-source-of-truth.md
git commit -m "docs: document read_model dict/model boundary convention

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Full-suite verification + grep audit

**Files:** none (verification only)

- [ ] **Step 1: Full orchestrator suite**

Run: `EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests -q`
Expected: PASS — branch base count plus the 7 new `read_model` tests; zero new failures. If a failure appears, compare against the branch base (`git stash` on a clean checkout of `origin/develop`) before treating it as a regression.

- [ ] **Step 2: Grep audit — migrated models no longer coerced ad-hoc**

Run: `grep -rnE "(MarketingCopy|CopySpec|TextLayoutSpec|TextStyleSpec|ImagePromptSpec|ImagePrompt|T2IRequest)\(\*\*" orchestrator/app --include="*.py"`
Expected: no output. Any match is a missed migration.

- [ ] **Step 3: Grep audit — read_model adoption**

Run: `grep -rc "read_model" orchestrator/app --include="*.py" | grep -v ":0" | sort -t: -k2 -rn`
Expected: `state.py` (definition + context_to_model delegation) plus the node files migrated in Tasks 2-3.

- [ ] **Step 4: Confirm clean tree (excluding the unrelated untracked plan file)**

Run: `git status --short`
Expected: only the untracked `docs/superpowers/plans/2026-06-13-generation-job-background-resume-reliability.md` line, nothing staged or modified.
