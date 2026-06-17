# Native Format Manual Review Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent GPT Image 2 native typography jobs from ending as empty failed results when the format-approved flyer/product-detail plan returns `manual_review`; route only that recoverable condition into the existing text-overlay generation pipeline.

**Architecture:** Keep the native typography lane unchanged for approved format plans. If `native_copy_brief` returns `native_generation_status == "manual_review"` because `format_approved_plan_bundle.decision == "manual_review"`, route to `copy_spec_parser` so the existing TLFP overlay path can still generate an output. Keep `rejected` and other native-copy/preflight manual-review states fail-closed through `native_result_adapter`.

**Tech Stack:** Python 3.12, LangGraph `StateGraph`, pytest, EasyAds orchestrator marketing graph.

---

## Scope Check

This plan touches only the orchestrator graph routing for native typography fallback. It does not change frontend UI, R2 upload logic, `generation_outputs` persistence, `native_result_adapter`, or result schema. The failed "Gangnam" job has no stored image (`image_call_count=0`, no outputs/assets), so historical recovery is out of scope; after this fix is deployed, that request must be rerun as a new generation job.

## File Structure

- Modify: `orchestrator/app/graph/routers.py`
  - Owns conditional route decisions between graph nodes.
  - Change `route_after_native_copy_brief()` so format-plan `manual_review` falls back to `copy_spec_parser`.

- Modify: `orchestrator/app/graph/builder.py`
  - Owns LangGraph node and edge registration.
  - Add the `native_copy_brief -> copy_spec_parser` conditional edge mapping.

- Modify: `orchestrator/tests/test_marketing_graph.py`
  - Owns marketing graph integration and route regression tests.
  - Add a focused router regression test and assert the new graph edge exists.

---

### Task 1: Add Failing Router Regression Test

**Files:**
- Modify: `orchestrator/tests/test_marketing_graph.py`
- Test: `orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline`

- [ ] **Step 1: Add the router import**

Find this import block near the "Task 9 production graph native typography wiring" section:

```python
import pytest as _pytest
from orchestrator.app.graph import builder as _production_graph_builder
from orchestrator.app.graph.routers import should_use_native_typography_lane as _should_use_native_lane
from orchestrator.app.graph.state import create_initial_marketing_state as _create_initial_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest as _InitialRequest, MarketingContext as _MarketingContext
```

Replace it with:

```python
import pytest as _pytest
from orchestrator.app.graph import builder as _production_graph_builder
from orchestrator.app.graph.routers import route_after_native_copy_brief as _route_after_native_copy_brief
from orchestrator.app.graph.routers import should_use_native_typography_lane as _should_use_native_lane
from orchestrator.app.graph.state import create_initial_marketing_state as _create_initial_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest as _InitialRequest, MarketingContext as _MarketingContext
```

- [ ] **Step 2: Add the failing test**

Find this existing test:

```python
@_pytest.mark.parametrize("unsupported", ["restaurant_poster", ""])
def test_native_route_condition_preserves_overlay_path_for_unsupported_formats(unsupported):
    assert _should_use_native_lane({"engine": "gpt_image_2", "selected_ad_format": unsupported}) is False
```

Immediately after it, add:

```python
def test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline():
    assert _route_after_native_copy_brief({
        "native_generation_status": "manual_review",
        "format_approved_plan_bundle": {"decision": "manual_review"},
    }) == "copy_spec_parser"
    assert _route_after_native_copy_brief({"native_generation_status": "manual_review"}) == "native_result_adapter"
    assert _route_after_native_copy_brief({"native_generation_status": "rejected"}) == "native_result_adapter"
```

- [ ] **Step 3: Run the new test and verify it fails**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline -q
```

Expected result before implementation:

```text
FAILED orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline
AssertionError: assert 'native_result_adapter' == 'copy_spec_parser'
```

Do not commit yet. The failing test proves the current graph sends recoverable format-plan `manual_review` to the failure adapter.

---

### Task 2: Add Graph Edge Regression Test

**Files:**
- Modify: `orchestrator/tests/test_marketing_graph.py`
- Test: `orchestrator/tests/test_marketing_graph.py::test_production_graph_registers_native_typography_nodes_and_edges`

- [ ] **Step 1: Update the expected edge set**

Find the edge assertions in `test_production_graph_registers_native_typography_nodes_and_edges()`:

```python
    assert {
        ("creative_execution_planner", "native_copy_brief"),
        ("native_copy_brief", "native_creative_preflight"),
        ("native_creative_preflight", "gpt_image_2_native_single_shot"),
        ("gpt_image_2_native_single_shot", "native_generation_review"),
        ("native_generation_review", "native_result_adapter"),
        ("native_result_adapter", "result"),
    } <= edges
```

Replace them with:

```python
    assert {
        ("creative_execution_planner", "native_copy_brief"),
        ("native_copy_brief", "native_creative_preflight"),
        ("native_copy_brief", "copy_spec_parser"),
        ("native_creative_preflight", "gpt_image_2_native_single_shot"),
        ("gpt_image_2_native_single_shot", "native_generation_review"),
        ("native_generation_review", "native_result_adapter"),
        ("native_result_adapter", "result"),
    } <= edges
```

- [ ] **Step 2: Run the graph edge test and verify it fails**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py::test_production_graph_registers_native_typography_nodes_and_edges -q
```

Expected result before implementation:

```text
FAILED orchestrator/tests/test_marketing_graph.py::test_production_graph_registers_native_typography_nodes_and_edges
AssertionError
```

Do not commit yet. The failing test proves LangGraph has no registered `native_copy_brief -> copy_spec_parser` path.

---

### Task 3: Implement Router Fallback For Format-Plan Manual Review

**Files:**
- Modify: `orchestrator/app/graph/routers.py`
- Test: `orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline`

- [ ] **Step 1: Replace the route function**

Find the current function:

```python
def route_after_native_copy_brief(state: MarketingState) -> str:
    return "native_creative_preflight" if state.get("native_generation_status") == "copy_approved" else "native_result_adapter"
```

Replace it with:

```python
def route_after_native_copy_brief(state: MarketingState) -> str:
    status = state.get("native_generation_status")
    if status == "copy_approved":
        return "native_creative_preflight"
    if status == "manual_review":
        bundle = state.get("format_approved_plan_bundle") or {}
        if isinstance(bundle, dict) and bundle.get("decision") == "manual_review":
            return "copy_spec_parser"
    return "native_result_adapter"
```

- [ ] **Step 2: Run the router test and verify it passes**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 3: Confirm non-format manual review remains fail-closed**

The test added in Task 1 already checks these two assertions:

```python
assert _route_after_native_copy_brief({"native_generation_status": "manual_review"}) == "native_result_adapter"
assert _route_after_native_copy_brief({"native_generation_status": "rejected"}) == "native_result_adapter"
```

If either assertion fails, restore the function from Step 1 exactly and rerun Step 2.

Do not commit yet. The graph builder still needs the new conditional edge.

---

### Task 4: Register The New LangGraph Conditional Edge

**Files:**
- Modify: `orchestrator/app/graph/builder.py`
- Test: `orchestrator/tests/test_marketing_graph.py::test_production_graph_registers_native_typography_nodes_and_edges`

- [ ] **Step 1: Update the conditional edge mapping**

Find this block in `build_marketing_graph()`:

```python
    graph.add_conditional_edges(
        "native_copy_brief",
        route_after_native_copy_brief,
        {"native_creative_preflight": "native_creative_preflight", "native_result_adapter": "native_result_adapter"},
    )
```

Replace it with:

```python
    graph.add_conditional_edges(
        "native_copy_brief",
        route_after_native_copy_brief,
        {
            "native_creative_preflight": "native_creative_preflight",
            "copy_spec_parser": "copy_spec_parser",
            "native_result_adapter": "native_result_adapter",
        },
    )
```

- [ ] **Step 2: Run both targeted graph tests**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline \
  orchestrator/tests/test_marketing_graph.py::test_production_graph_registers_native_typography_nodes_and_edges \
  -q
```

Expected result:

```text
2 passed
```

- [ ] **Step 3: Commit the routing fix**

Run:

```bash
git add orchestrator/app/graph/routers.py orchestrator/app/graph/builder.py orchestrator/tests/test_marketing_graph.py
git commit -m "fix(orchestrator): fallback format manual review to overlay pipeline"
```

Expected result:

```text
[branch-name commit-sha] fix(orchestrator): fallback format manual review to overlay pipeline
```

---

### Task 5: Run Regression Tests For Native Typography Safety

**Files:**
- Test: `orchestrator/tests/test_marketing_graph.py`
- Test: `orchestrator/tests/test_format_approved_plan_service.py`
- Test: `orchestrator/tests/test_gpt_image2_native_single_shot.py`

- [ ] **Step 1: Run focused safety regressions**

Run:

```bash
PYTHONPATH=. uv run pytest \
  orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_node_fails_closed_on_non_approved_bundle \
  orchestrator/tests/test_marketing_graph.py::test_production_graph_rejects_invented_flyer_operational_text_before_image \
  orchestrator/tests/test_format_approved_plan_service.py::test_ambiguous_flyer_mode_conflict_returns_manual_review \
  orchestrator/tests/test_gpt_image2_native_single_shot.py::test_pipeline_invented_operational_text_fails_closed_before_preflight \
  -q
```

Expected result:

```text
4 passed
```

- [ ] **Step 2: Run the broader related test files**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py orchestrator/tests/test_gpt_image2_native_single_shot.py
```

Expected result:

```text
57 passed
```

Warnings from Pillow deprecations are acceptable for this plan because they pre-exist and do not affect the routing behavior.

- [ ] **Step 3: Inspect the final diff**

Run:

```bash
git diff --stat HEAD~1..HEAD
git show --name-only --oneline HEAD
```

Expected changed files:

```text
orchestrator/app/graph/builder.py
orchestrator/app/graph/routers.py
orchestrator/tests/test_marketing_graph.py
```

---

### Task 6: Deploy And Verify The Gangnam Failure Mode No Longer Produces An Empty Failed Job

**Files:**
- No source files.
- Operational verification uses the deployed orchestrator environment.

- [ ] **Step 1: Deploy the orchestrator commit**

Deploy the commit from Task 4 to the environment that runs generation jobs. Restart both the orchestrator API and any worker/background process that invokes `build_marketing_graph()`.

Run this local sanity command after deployment artifact creation, before traffic cutover:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_marketing_graph.py::test_native_copy_brief_manual_review_falls_back_to_overlay_pipeline -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 2: Rerun the failed Gangnam request as a new job**

Use the app UI or the existing admin/job retry path to create a new generation job for the same thread:

```text
thread_0933c77e0ae642fd90d9700aea42393c
```

Use the same captured user inputs:

```text
user_input: 강남역 원어민 영어 회화반 직장인 수강생 모집 광고 만들어줘.
business_type: academy
item_or_service: 교육
promotion_goal: reservation_cta
ad_format: flyer
copy_generation_mode: custom_input
user_custom_headline: 공부하자
user_custom_subcopy: 놀지말고
```

Expected runtime behavior:

```text
native_copy_brief may produce format_approved_plan_bundle.decision=manual_review
route_after_native_copy_brief returns copy_spec_parser
the job continues through the TLFP overlay pipeline
image_call_count is not reported as a native GPT Image 2 call for the failed branch
the final result has output_path or final_image_path
```

- [ ] **Step 3: Verify database output exists for the new job**

Run this SQL in the deployed database console:

```sql
select
  gj.public_job_id,
  gj.status,
  gj.current_stage,
  gj.output_path,
  gj.result_payload ->> 'status' as result_status,
  gj.result_payload ->> 'output_path' as result_output_path,
  gj.error
from generation_jobs gj
join chat_threads ct on ct.id = gj.thread_id
where ct.public_thread_id = 'thread_0933c77e0ae642fd90d9700aea42393c'
order by gj.created_at desc
limit 5;
```

Expected result for the newest row:

```text
status is done
output_path is not null, or result_output_path is not null
error is null or empty
```

Run this SQL to confirm an output row exists:

```sql
select
  go.public_output_id,
  go.output_type,
  go.is_final,
  go.asset_id,
  go.result_payload ->> 'final_image_path' as final_image_path,
  go.result_payload ->> 'final_image_url' as final_image_url
from generation_outputs go
join generation_jobs gj on gj.id = go.job_id
join chat_threads ct on ct.id = gj.thread_id
where ct.public_thread_id = 'thread_0933c77e0ae642fd90d9700aea42393c'
order by go.created_at desc
limit 5;
```

Expected result for the newest rerun:

```text
at least one row exists
is_final is true for the selected final output
final_image_path or final_image_url is present
```

- [ ] **Step 4: Verify the old failed job remains unchanged**

Run this SQL:

```sql
select
  public_job_id,
  status,
  output_path,
  result_payload,
  error
from generation_jobs
where public_job_id = 'job_c22cc042c87d4a73a2d34319510d3c37';
```

Expected result:

```text
status remains failed
output_path remains null
error still records the original manual_review failure
```

This confirms the fix does not fabricate an output for a job that never generated an image.

---

## Self-Review

**Spec coverage:** The plan covers the root cause, router change, graph edge registration, targeted tests, broader regression tests, deployment, rerun, and database verification. Historical asset recovery is explicitly excluded because the old job has no image or asset row.

**Placeholder scan:** The plan contains no deferred-work markers or vague "add tests" steps. Every code edit includes exact replacement code, and every test command includes expected output.

**Type consistency:** Route return values match existing graph node names: `native_creative_preflight`, `copy_spec_parser`, and `native_result_adapter`. State keys match existing graph state: `native_generation_status` and `format_approved_plan_bundle`.
