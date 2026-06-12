# Orchestrator Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate seven low-risk code-quality debts in the orchestrator: dotenv re-reading on every env lookup, the run_mode elif chain, the implicit `**`-unpack in `validate_output`, inline `import re`, dead `hasattr` checks, duplicate `append_*` function names, and the hardcoded dirty-field if-chain.

**Architecture:** Each task is an isolated, behavior-preserving refactor (except `validate_output`, which gains a clearer error message on the same failure path). No public API changes. Tests are added/extended per task; the existing 22-passing baseline (`test_langgraph_state.py`, `test_llm_node_runner.py`, `test_generation_job_graph_execution.py`) must stay green throughout.

**Tech Stack:** Python 3.12, FastAPI, LangGraph 1.1.3, Pydantic 2, pytest via `uv run python -m pytest`.

**Important conventions for this codebase:**
- Run all tests with `uv run python -m pytest <path> -q` from the repo root `/home/spai0710/pjt-sprint_ai07_easyadsAGENT`.
- 58 test files monkeypatch env vars via `os.environ` / `monkeypatch.setenv`. **Never cache the result of an `os.environ` lookup** — only file parsing may be cached (Task 1 relies on this distinction).
- Commit messages follow conventional commits with scopes, e.g. `refactor(config): ...` (see `git log --oneline` for examples).

---

### Task 1: Cache dotenv file parsing in `core/config.py`

`_get_env()` re-reads and re-parses `.env` and `docs/api_key.env` from disk on every call. Settings constructors call `_get_env` dozens of times per request. Fix: cache the **file parsing** only. `os.environ` is still consulted live on every call, so the 58 test files that monkeypatch env vars are unaffected.

**Files:**
- Modify: `orchestrator/app/core/config.py:13-24`
- Create: `orchestrator/tests/test_core_config.py`

- [ ] **Step 1: Write the failing test**

Create `orchestrator/tests/test_core_config.py`:

```python
"""Tests for core config env loading and dotenv caching."""

from orchestrator.app.core.config import _get_env, _load_dotenv


def test_load_dotenv_caches_file_parse(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n")
    _load_dotenv.cache_clear()

    first = _load_dotenv(env_file)
    assert first["FOO"] == "bar"

    # Mutate the file; the cached parse must be returned (process-lifetime cache).
    env_file.write_text("FOO=changed\n")
    second = _load_dotenv(env_file)
    assert second is first
    assert second["FOO"] == "bar"

    _load_dotenv.cache_clear()


def test_load_dotenv_missing_file_returns_empty(tmp_path):
    _load_dotenv.cache_clear()
    assert _load_dotenv(tmp_path / "does_not_exist.env") == {}
    _load_dotenv.cache_clear()


def test_get_env_prefers_live_os_environ(monkeypatch):
    monkeypatch.setenv("EASYADS_TEST_CONFIG_KEY", "from-os")
    assert _get_env("EASYADS_TEST_CONFIG_KEY", "default") == "from-os"
    # Changing os.environ must be visible immediately (no caching of env lookups).
    monkeypatch.setenv("EASYADS_TEST_CONFIG_KEY", "from-os-2")
    assert _get_env("EASYADS_TEST_CONFIG_KEY", "default") == "from-os-2"


def test_get_env_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("EASYADS_TEST_CONFIG_KEY_ABSENT", raising=False)
    assert _get_env("EASYADS_TEST_CONFIG_KEY_ABSENT", "fallback") == "fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest orchestrator/tests/test_core_config.py -q`
Expected: FAIL — `AttributeError: 'function' object has no attribute 'cache_clear'` (because `_load_dotenv` is not yet wrapped in `lru_cache`).

- [ ] **Step 3: Add `lru_cache` to `_load_dotenv`**

In `orchestrator/app/core/config.py`, add the import near the top of the file (after `import os` / `from pathlib import Path` block):

```python
from functools import lru_cache
```

Then decorate `_load_dotenv` (currently at line 13) and document the cache contract:

```python
@lru_cache(maxsize=None)
def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a dotenv file once per process.

    Cached for the process lifetime: dotenv files are deployment-time inputs,
    not runtime-mutable state. os.environ is NOT cached — _get_env always
    checks it live, so monkeypatched env vars in tests keep working.
    Callers must treat the returned dict as read-only.
    """
```

Keep the existing function body unchanged below the docstring.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest orchestrator/tests/test_core_config.py orchestrator/tests/test_llm_settings.py orchestrator/tests/test_t2i_settings.py orchestrator/tests/test_db_settings.py -q`
Expected: PASS (all). The three settings test files prove the env-precedence contract is intact.

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/core/config.py orchestrator/tests/test_core_config.py
git commit -m "refactor(config): cache dotenv file parsing per process

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Replace run_mode elif chain with a mapping dict

`create_generation_job_route` routes 13 t2i run_mode strings to 4 engines through five elif branches (`orchestrator/app/api/routers/generation_jobs.py:148-157`). Replace with a module-level mapping.

**Files:**
- Modify: `orchestrator/app/api/routers/generation_jobs.py:142-158`
- Create: `orchestrator/tests/test_generation_job_run_mode_mapping.py`

- [ ] **Step 1: Write the failing test**

Create `orchestrator/tests/test_generation_job_run_mode_mapping.py`:

```python
"""Characterization test for run_mode -> t2i engine routing."""

from orchestrator.app.api.routers.generation_jobs import T2I_RUN_MODE_TO_ENGINE


def test_run_mode_mapping_matches_legacy_elif_chain():
    # Exact behavior of the elif chain this mapping replaced.
    expected = {
        "gpt_image_1_actual": "gpt_image_1",
        "gpt_image_1_smoke": "gpt_image_1",
        "gpt_image_2_actual": "gpt_image_2",
        "gpt_image_2_smoke": "gpt_image_2",
        "sd35_local": "sd35_large",
        "sd35_local_smoke": "sd35_large",
        "sd35_large_real": "sd35_large",
        "flux2_klein_4b": "flux2_klein_4b",
        "flux_local": "flux2_klein_4b",
        "flux_local_smoke": "flux2_klein_4b",
        "flux_schnell_real": "flux2_klein_4b",
        "flux": "flux2_klein_4b",
        "flux_smoke": "flux2_klein_4b",
    }
    assert T2I_RUN_MODE_TO_ENGINE == expected


def test_non_t2i_modes_not_in_mapping():
    for mode in ("mock_immediate", "graph_job"):
        assert mode not in T2I_RUN_MODE_TO_ENGINE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest orchestrator/tests/test_generation_job_run_mode_mapping.py -q`
Expected: FAIL — `ImportError: cannot import name 'T2I_RUN_MODE_TO_ENGINE'`.

- [ ] **Step 3: Add the mapping and replace the elif chain**

In `orchestrator/app/api/routers/generation_jobs.py`, add at module level (after the existing imports, before `_request_principal`):

```python
# run_mode aliases -> t2i engine. Non-t2i modes (mock_immediate, graph_job,
# modal routing) are handled explicitly in create_generation_job_route.
T2I_RUN_MODE_TO_ENGINE: dict[str, str] = {
    "gpt_image_1_actual": "gpt_image_1",
    "gpt_image_1_smoke": "gpt_image_1",
    "gpt_image_2_actual": "gpt_image_2",
    "gpt_image_2_smoke": "gpt_image_2",
    "sd35_local": "sd35_large",
    "sd35_local_smoke": "sd35_large",
    "sd35_large_real": "sd35_large",
    "flux2_klein_4b": "flux2_klein_4b",
    "flux_local": "flux2_klein_4b",
    "flux_local_smoke": "flux2_klein_4b",
    "flux_schnell_real": "flux2_klein_4b",
    "flux": "flux2_klein_4b",
    "flux_smoke": "flux2_klein_4b",
}
```

Then replace lines 148-157 (the five t2i elif branches, starting with `elif request.run_mode in {"gpt_image_1_actual", ...}` and ending with the flux branch) with:

```python
    elif request.run_mode in T2I_RUN_MODE_TO_ENGINE:
        job = execute_generation_job_t2i(job.job_id, request, engine_name=T2I_RUN_MODE_TO_ENGINE[request.run_mode])
```

The `should_route_generation_job_to_modal` / `mock_immediate` / `graph_job` branches above it stay exactly as they are.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest orchestrator/tests/test_generation_job_run_mode_mapping.py orchestrator/tests/test_api_generation_jobs_router.py orchestrator/tests/test_api_contract_generation_jobs.py orchestrator/tests/test_generation_job_flux_lane.py orchestrator/tests/test_generation_job_actual_lanes.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/api/routers/generation_jobs.py orchestrator/tests/test_generation_job_run_mode_mapping.py
git commit -m "refactor(api): map run_mode to t2i engine via dict

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Explicit non-mapping guard in `validate_output`

`validate_output` (`orchestrator/app/llm/node_runner.py:124-129`) does `output_schema(**(output or {}))`. If an LLM returns a list, this raises a bare `TypeError` that the caller's `except Exception` turns into a silent fallback. Keep the fallback path (intended behavior) but raise a clear `ValueError` so logs/metadata show what happened.

**Files:**
- Modify: `orchestrator/app/llm/node_runner.py:124-129`
- Test: `orchestrator/tests/test_llm_node_runner.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `orchestrator/tests/test_llm_node_runner.py`:

```python
def test_validate_output_rejects_non_mapping_with_clear_error():
    import pytest
    from pydantic import BaseModel

    from orchestrator.app.llm.node_runner import validate_output

    class _Out(BaseModel):
        value: int = 0

    with pytest.raises(ValueError, match="must be a mapping"):
        validate_output(_Out, ["not", "a", "mapping"])


def test_validate_output_accepts_none_and_mapping():
    from pydantic import BaseModel

    from orchestrator.app.llm.node_runner import validate_output

    class _Out(BaseModel):
        value: int = 0

    assert validate_output(_Out, None).value == 0
    assert validate_output(_Out, {"value": 3}).value == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest orchestrator/tests/test_llm_node_runner.py -q`
Expected: FAIL — the first new test fails because a `TypeError` is raised instead of `ValueError` (pytest reports the TypeError, not a match failure).

- [ ] **Step 3: Add the explicit Mapping check**

In `orchestrator/app/llm/node_runner.py`, add to the imports at the top of the file:

```python
from collections.abc import Mapping
```

Replace the `validate_output` function (lines 124-129):

```python
def validate_output(output_schema: Any, output: Any) -> Any:
    if isinstance(output_schema, type) and issubclass(output_schema, BaseModel):
        if isinstance(output, output_schema):
            return output
        if output is not None and not isinstance(output, Mapping):
            # Intentionally raised so the caller's except-path records a clear
            # fallback_reason instead of an opaque TypeError from ** unpacking.
            raise ValueError(
                f"LLM output for {output_schema.__name__} must be a mapping, got {type(output).__name__}"
            )
        return output_schema(**(output or {}))
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest orchestrator/tests/test_llm_node_runner.py -q`
Expected: PASS (all, including pre-existing tests — the fallback path still triggers on the exception).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/llm/node_runner.py orchestrator/tests/test_llm_node_runner.py
git commit -m "refactor(llm): raise explicit error for non-mapping LLM output

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Hoist inline `import re` in `copy_candidates.py`

`re` is imported inside `re_search_phone` and `re_search_price` (`orchestrator/app/llm/nodes/copy_candidates.py:168,174`). Standard library imports belong at module top.

**Files:**
- Modify: `orchestrator/app/llm/nodes/copy_candidates.py:1-20,167-178`

- [ ] **Step 1: Move the import**

In `orchestrator/app/llm/nodes/copy_candidates.py`, add after `from __future__ import annotations`:

```python
import re
```

Then replace both functions (currently around lines 167-178):

```python
def re_search_phone(text: str) -> bool:
    return bool(re.search(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}", text or ""))


def re_search_price(text: str) -> bool:
    return bool(re.search(r"(₩\s*\d|[0-9][0-9,]*\s*원)", text or ""))
```

(The only change is deleting the two `import re` lines inside the function bodies; regexes are byte-for-byte identical.)

- [ ] **Step 2: Run the copy-related tests**

Run: `uv run python -m pytest orchestrator/tests -k "copy" -q`
Expected: PASS (all collected copy tests; this includes `test_copy_llm_v1.py` and candidate-quality tests).

- [ ] **Step 3: Commit**

```bash
git add orchestrator/app/llm/nodes/copy_candidates.py
git commit -m "refactor(llm): hoist inline re imports to module top

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Remove dead `hasattr` checks in `create_initial_marketing_state`

`source_asset_id` and `reference_asset_id` are declared on `InitialMarketingRequest` (`orchestrator/app/schemas/llm_marketing.py:195-196`), so the four `hasattr` guards in `orchestrator/app/graph/state.py:267-268,304-305` are dead code.

**Files:**
- Modify: `orchestrator/app/graph/state.py:267-268,304-305`
- Test: `orchestrator/tests/test_langgraph_state.py` (append)

- [ ] **Step 1: Write the regression test**

Append to `orchestrator/tests/test_langgraph_state.py`:

```python
def test_initial_state_carries_asset_ids():
    from orchestrator.app.graph.state import create_initial_marketing_state
    from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest

    request = InitialMarketingRequest(
        user_input="카페 신메뉴 홍보",
        source_asset_id="asset-src-1",
        reference_asset_id="asset-ref-1",
    )
    state = create_initial_marketing_state(request)
    assert state["source_asset_id"] == "asset-src-1"
    assert state["reference_asset_id"] == "asset-ref-1"
    assert state["current_brief"]["source_asset_id"] == "asset-src-1"
    assert state["current_brief"]["reference_asset_id"] == "asset-ref-1"
```

- [ ] **Step 2: Run test to verify it passes already (characterization)**

Run: `uv run python -m pytest orchestrator/tests/test_langgraph_state.py -q`
Expected: PASS. (This test locks current behavior before the refactor — it must still pass after.)

- [ ] **Step 3: Replace the four hasattr expressions**

In `orchestrator/app/graph/state.py`, inside `create_initial_marketing_state`, both the `current_brief` dict (lines 267-268) and the `state` dict (lines 304-305) contain this identical pair — replace **both occurrences**:

```python
        "source_asset_id": request.source_asset_id if hasattr(request, "source_asset_id") else None,
        "reference_asset_id": request.reference_asset_id if hasattr(request, "reference_asset_id") else None,
```

with:

```python
        "source_asset_id": request.source_asset_id,
        "reference_asset_id": request.reference_asset_id,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest orchestrator/tests/test_langgraph_state.py orchestrator/tests/test_marketing_state_model_policy.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_langgraph_state.py
git commit -m "refactor(graph): drop dead hasattr guards for declared request fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Rename node_runner's shadowing `append_*` helpers

`append_model_selection` / `append_llm_call_result` exist in both `orchestrator/app/graph/state.py:420,426` and `orchestrator/app/llm/node_runner.py:139,144` with **intentionally different behavior** (node_runner's version sanitizes via `safe_llm_call_result`). Do NOT merge them — rename node_runner's to make the sanitization explicit and kill the name collision.

**Files:**
- Modify: `orchestrator/app/llm/node_runner.py:44,72,107,139,144`
- Modify: `orchestrator/tests/test_copy_llm_v1.py:2,127`

- [ ] **Step 1: Verify the only external importer**

Run: `grep -rn "from orchestrator.app.llm.node_runner import" orchestrator --include="*.py" | grep -E "append_model_selection|append_llm_call_result"`
Expected output (exactly one line):
```
orchestrator/tests/test_copy_llm_v1.py:2:from orchestrator.app.llm.node_runner import append_llm_call_result
```
If more lines appear, update those import sites the same way as Step 4 before continuing.

- [ ] **Step 2: Rename the definitions in node_runner.py**

In `orchestrator/app/llm/node_runner.py` (lines 139-146), rename:

```python
def append_model_selection_safe(state: dict[str, Any], selection: Any) -> None:
    state.setdefault("model_selections", [])
    state["model_selections"].append(selection.model_dump() if hasattr(selection, "model_dump") else selection)


def append_llm_call_result_safe(state: dict[str, Any], result: Any) -> None:
    state.setdefault("llm_call_results", [])
    state["llm_call_results"].append(safe_llm_call_result(result))
```

(Bodies unchanged; only the names gain the `_safe` suffix. Unlike `orchestrator/app/graph/state.py`'s versions, these sanitize the payload and skip the `updated_at` bump — that difference is now visible in the name.)

- [ ] **Step 3: Update the three internal call sites**

In the same file:
- Line 44: `append_model_selection(state, selection)` → `append_model_selection_safe(state, selection)`
- Lines 72 and 107: `append_llm_call_result(state, result)` → `append_llm_call_result_safe(state, result)` (two occurrences, replace both)

- [ ] **Step 4: Update the test import**

In `orchestrator/tests/test_copy_llm_v1.py`:
- Line 2: `from orchestrator.app.llm.node_runner import append_llm_call_result` → `from orchestrator.app.llm.node_runner import append_llm_call_result_safe`
- Line 127: `append_llm_call_result(` → `append_llm_call_result_safe(`

- [ ] **Step 5: Verify no stale references remain**

Run: `grep -rn "append_model_selection\b\|append_llm_call_result\b" orchestrator/app/llm/node_runner.py`
Expected: no output (all occurrences now carry the `_safe` suffix).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run python -m pytest orchestrator/tests/test_llm_node_runner.py orchestrator/tests/test_copy_llm_v1.py orchestrator/tests/test_marketing_state_model_policy.py -q`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add orchestrator/app/llm/node_runner.py orchestrator/tests/test_copy_llm_v1.py
git commit -m "refactor(llm): rename sanitizing append helpers to resolve name shadowing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Declarative dirty-field propagation rules

`calculate_dirty_fields` (`orchestrator/app/graph/state.py:440-458`) encodes "if A changed, B/C/D are dirty" as seven nested if-blocks. Convert to a declarative rules table with identical semantics (single-pass, non-transitive).

**Files:**
- Modify: `orchestrator/app/graph/state.py:440-458`
- Create: `orchestrator/tests/test_dirty_field_propagation.py`

- [ ] **Step 1: Write characterization tests against the CURRENT implementation**

Create `orchestrator/tests/test_dirty_field_propagation.py`:

```python
"""Characterization tests for dirty-field propagation (locked before refactor)."""

import pytest

from orchestrator.app.graph.state import calculate_dirty_fields


@pytest.mark.parametrize(
    "changed, expected",
    [
        ([], []),
        (["unknown_field"], ["unknown_field"]),
        (
            ["brand_tone"],
            sorted({
                "brand_tone", "marketing_copy", "copywriting_output",
                "image_prompt", "prompt_render_output",
                "text_style_spec", "text_layout_spec", "image_prompt_spec",
            }),
        ),
        (
            ["ad_format"],
            sorted({
                "ad_format", "image_prompt", "prompt_render_output",
                "ad_format_spec", "layout_spec",
                "text_layout_spec", "image_prompt_spec", "t2i_request",
            }),
        ),
        (
            ["business_type"],
            sorted({"business_type", "image_prompt", "prompt_render_output"}),
        ),
        (
            ["copy_generation_mode"],
            sorted({
                "copy_generation_mode", "marketing_copy", "copy_spec",
                "text_layout_spec", "image_prompt_spec", "prompt_render_output",
            }),
        ),
        (
            ["price_or_discount"],
            sorted({
                "price_or_discount", "copy_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output", "t2i_request",
            }),
        ),
        (
            ["region_type"],
            sorted({
                "region_type", "text_style_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output",
            }),
        ),
        # Propagation is single-pass: marketing_copy as a *trigger* dirties copy
        # specs, but does NOT transitively re-trigger other rules' outputs.
        (
            ["marketing_copy"],
            sorted({
                "marketing_copy", "copy_spec", "text_layout_spec",
                "image_prompt_spec", "prompt_render_output", "t2i_request",
            }),
        ),
    ],
)
def test_dirty_propagation(changed, expected):
    assert calculate_dirty_fields({}, changed) == expected


def test_multiple_changed_fields_union():
    result = calculate_dirty_fields({}, ["brand_tone", "ad_format"])
    expected = sorted(
        set(calculate_dirty_fields({}, ["brand_tone"]))
        | set(calculate_dirty_fields({}, ["ad_format"]))
    )
    assert result == expected
```

- [ ] **Step 2: Run against the current if-chain — must already pass**

Run: `uv run python -m pytest orchestrator/tests/test_dirty_field_propagation.py -q`
Expected: PASS (10 tests). If any fail, the expected sets above are wrong — fix the test to match actual current output (this is a characterization test; current behavior is the spec) before touching the implementation.

- [ ] **Step 3: Replace the if-chain with a rules table**

In `orchestrator/app/graph/state.py`, replace `calculate_dirty_fields` (lines 440-458) with:

```python
# Declarative dirty-field propagation: (trigger fields, fields invalidated when
# any trigger changes). Single-pass and non-transitive by design — derived
# fields appearing as triggers (e.g. marketing_copy) only fire when explicitly
# listed in changed_fields, mirroring the legacy if-chain.
DIRTY_PROPAGATION_RULES: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"brand_tone", "target_persona", "promotion_goal", "usp", "item_or_service"}),
        frozenset({"marketing_copy", "copywriting_output"}),
    ),
    (
        frozenset({"business_type", "brand_tone", "ad_format", "usp"}),
        frozenset({"image_prompt", "prompt_render_output"}),
    ),
    (
        frozenset({"ad_format"}),
        frozenset({"ad_format_spec", "layout_spec"}),
    ),
    (
        frozenset({"marketing_copy", "copywriting_output", "item_or_service", "promotion_goal", "price_or_discount"}),
        frozenset({"copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"}),
    ),
    (
        frozenset({"brand_tone", "target_persona", "region_type", "usp"}),
        frozenset({"text_style_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"}),
    ),
    (
        frozenset({"ad_format", "layout_spec", "ad_format_spec"}),
        frozenset({"text_layout_spec", "image_prompt_spec", "prompt_render_output", "t2i_request"}),
    ),
    (
        frozenset({"copy_generation_mode", "user_custom_headline", "user_custom_subcopy"}),
        frozenset({"marketing_copy", "copy_spec", "text_layout_spec", "image_prompt_spec", "prompt_render_output"}),
    ),
)


def calculate_dirty_fields(state: MarketingState, changed_fields: list[str] | None = None) -> list[str]:
    changed = set(changed_fields or [])
    dirty: set[str] = set(changed)
    for triggers, outputs in DIRTY_PROPAGATION_RULES:
        if changed & triggers:
            dirty.update(outputs)
    return sorted(dirty)
```

- [ ] **Step 4: Run tests to verify identical behavior**

Run: `uv run python -m pytest orchestrator/tests/test_dirty_field_propagation.py orchestrator/tests/test_langgraph_state.py -q`
Expected: PASS (all — the characterization tests prove the rules table is semantically identical to the if-chain).

- [ ] **Step 5: Commit**

```bash
git add orchestrator/app/graph/state.py orchestrator/tests/test_dirty_field_propagation.py
git commit -m "refactor(graph): declare dirty-field propagation as rules table

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full orchestrator test suite**

Run: `uv run python -m pytest orchestrator/tests -q`
Expected: PASS — same pass count as on the branch base, plus the ~18 new tests added by Tasks 1-7. Zero new failures. If anything fails, fix it within the task that introduced it before proceeding.

- [ ] **Step 2: Confirm clean tree**

Run: `git status --short`
Expected: empty output (everything committed task-by-task).
