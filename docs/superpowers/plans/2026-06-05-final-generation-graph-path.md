# Final Generation Graph Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the UI final generation action execute the full LangGraph marketing generation chain instead of the direct T2I bridge, while preserving GPT-image-2, FLUX.1-schnell, and SD3.5 Large as selectable engines.

**Architecture:** The frontend will always create final generation jobs with `runMode: "graph_immediate"` and pass the selected image engine through sanitized metadata. The orchestrator generation job service will normalize that selected engine, persist it into the input state snapshot, and `execute_generation_job_graph()` will restore it so the graph's `t2i_request_builder` and `t2i_generation` nodes receive the selected engine. Direct T2I run modes remain available for smoke/debug paths but are no longer used by the main UI final generation flow.

**Tech Stack:** Next.js/React/TypeScript, Vitest, FastAPI/Pydantic, LangGraph, Pytest.

---

## Scope

This is the 1st phase only.

Included:
- Final UI generation requests use `graph_immediate`.
- Selected UI engine is propagated as a graph engine preference.
- Generation job input snapshots include `engine`.
- Coverage diagnostics mark final generation as `generation-job-graph`.
- Existing direct T2I run modes remain for backend smoke/debug tests.

Excluded:
- A new generation-job resume endpoint for `waiting_user_input`.
- UI for answering questions after a generation job has already entered `waiting_user_input`.
- Refactoring the existing chat/photo APIs into generation-jobs.

## File Structure

- Modify: `apps/web/lib/generation-engine.ts`
  - Keep UI engine options.
  - Add graph run mode helper.
  - Add backend engine preference helper.
- Modify: `apps/web/lib/generation-engine.test.ts`
  - Verify final UI run mode is `graph_immediate`.
  - Verify UI engine IDs map to backend engine preferences.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Use `graph_immediate` for final generation.
  - Add `requested_engine` and `t2i_engine` metadata.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Update final generation assertions.
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.ts`
  - Mark final generation as graph-backed.
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`
  - Assert the graph path is now covered.
- Modify: `orchestrator/app/generation_jobs/service.py`
  - Normalize selected engine metadata.
  - Persist selected engine into job metadata and input state snapshot.
- Modify: `orchestrator/app/chat_threads/state_snapshot.py`
  - Persist top-level `engine` when chat state snapshots are serialized/restored.
- Modify: `orchestrator/tests/test_generation_job_service.py`
  - Verify `graph_immediate` snapshot includes selected engine.
- Modify: `orchestrator/tests/test_generation_job_graph_execution.py`
  - Verify graph executor receives selected engine.
- Modify: `orchestrator/tests/test_api_generation_jobs_router.py`
  - Verify router sends `graph_immediate` requests to graph executor.

---

### Task 1: Frontend Engine Contract

**Files:**
- Modify: `apps/web/lib/generation-engine.ts`
- Test: `apps/web/lib/generation-engine.test.ts`

- [ ] **Step 1: Write the failing test**

Replace the first test in `apps/web/lib/generation-engine.test.ts` with:

```ts
it("uses the LangGraph run mode for final UI generation", () => {
  expect(resolveGenerationRunMode("gpt_image_2")).toBe("graph_immediate");
  expect(resolveGenerationRunMode("flux_schnell")).toBe("graph_immediate");
  expect(resolveGenerationRunMode("sd35_large")).toBe("graph_immediate");
});
```

Add this test below it:

```ts
it("maps UI engine choices to backend graph engine preferences", () => {
  expect(resolveGenerationEnginePreference("gpt_image_2")).toBe("gpt_image_2");
  expect(resolveGenerationEnginePreference("flux_schnell")).toBe("flux");
  expect(resolveGenerationEnginePreference("sd35_large")).toBe("sd35_large");
});
```

Update the import list in the same test file:

```ts
import {
  DEFAULT_IMAGE_GENERATION_ENGINE,
  getGenerationEngineOption,
  isTerminalGenerationJobStatus,
  resolveGenerationEnginePreference,
  resolveGenerationRunMode
} from "./generation-engine";
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm test -- --run lib/generation-engine.test.ts
```

Expected: FAIL because `resolveGenerationRunMode()` still returns direct T2I run modes and `resolveGenerationEnginePreference()` does not exist.

- [ ] **Step 3: Implement the minimal frontend contract**

Update `apps/web/lib/generation-engine.ts` to this shape:

```ts
export type ImageGenerationEngine = "gpt_image_2" | "flux_schnell" | "sd35_large";

export type GenerationRunMode = "graph_immediate";
export type DirectGenerationRunMode = "gpt_image_2_actual" | "flux_schnell_real" | "sd35_large_real";
export type BackendImageEngine = "gpt_image_2" | "flux" | "sd35_large";

export type GenerationEngineOption = {
  id: ImageGenerationEngine;
  label: string;
  modelName: string;
  description: string;
  backendEngine: BackendImageEngine;
  directRunMode: DirectGenerationRunMode;
};

export const DEFAULT_IMAGE_GENERATION_ENGINE: ImageGenerationEngine = "gpt_image_2";

export const generationEngineOptions: GenerationEngineOption[] = [
  {
    id: "gpt_image_2",
    label: "고품질 이미지",
    modelName: "GPT-image-2",
    description: "완성도 높은 광고 시안에 적합해요.",
    backendEngine: "gpt_image_2",
    directRunMode: "gpt_image_2_actual"
  },
  {
    id: "flux_schnell",
    label: "빠른 생성",
    modelName: "FLUX.1-schnell",
    description: "빠르게 여러 방향을 확인할 때 좋아요.",
    backendEngine: "flux",
    directRunMode: "flux_schnell_real"
  },
  {
    id: "sd35_large",
    label: "정교한 이미지",
    modelName: "SD3.5 Large",
    description: "디테일한 이미지 구성이 필요할 때 사용해요.",
    backendEngine: "sd35_large",
    directRunMode: "sd35_large_real"
  }
];

export function getGenerationEngineOption(engine: ImageGenerationEngine | null | undefined): GenerationEngineOption {
  return generationEngineOptions.find((option) => option.id === engine) ?? generationEngineOptions[0];
}

export function resolveGenerationRunMode(_engine: ImageGenerationEngine | null | undefined): GenerationRunMode {
  return "graph_immediate";
}

export function resolveGenerationEnginePreference(engine: ImageGenerationEngine | null | undefined): BackendImageEngine {
  return getGenerationEngineOption(engine).backendEngine;
}

export function resolveDirectGenerationRunMode(engine: ImageGenerationEngine | null | undefined): DirectGenerationRunMode {
  return getGenerationEngineOption(engine).directRunMode;
}

export function isTerminalGenerationJobStatus(status: string | null | undefined): boolean {
  return status === "done" || status === "completed" || status === "failed" || status === "cancelled";
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
npm test -- --run lib/generation-engine.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/generation-engine.ts apps/web/lib/generation-engine.test.ts
git commit -m "feat(web): route final generation through graph mode"
```

---

### Task 2: UI Final Generation Payload

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write the failing test**

In the final generation assertion inside `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, replace the expected payload fragment:

```ts
runMode: "gpt_image_2_actual",
```

with:

```ts
runMode: "graph_immediate",
```

Replace the metadata expectation with:

```ts
metadata: expect.objectContaining({
  selected_engine: "gpt_image_2",
  requested_engine: "gpt_image_2",
  t2i_engine: "gpt_image_2",
  selected_engine_label: "GPT-image-2",
  selected_channel_id: "instagram-story",
  selected_tone: "상큼한"
})
```

Remove this assertion:

```ts
expect(vi.mocked(api.createGenerationJob).mock.calls[0][0].runMode).not.toBe("graph_immediate");
```

Update the FLUX test expectation from:

```ts
runMode: "flux_schnell_real",
```

to:

```ts
runMode: "graph_immediate",
```

and add:

```ts
metadata: expect.objectContaining({
  selected_engine: "flux_schnell",
  requested_engine: "flux",
  t2i_engine: "flux"
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: FAIL because the component still sends direct T2I run modes and lacks backend engine metadata.

- [ ] **Step 3: Implement the payload change**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, update the generation engine import:

```ts
import {
  DEFAULT_IMAGE_GENERATION_ENGINE,
  getGenerationEngineOption,
  isTerminalGenerationJobStatus,
  resolveGenerationEnginePreference,
  resolveGenerationRunMode
} from "@/lib/generation-engine";
```

In `handleOpenGeneratedResult()`, add:

```ts
const backendEngine = resolveGenerationEnginePreference(engine);
```

Then update the `createGenerationJob()` payload metadata:

```ts
const created = await createGenerationJob({
  userInput: requestUserInput,
  threadId: state.threadId || undefined,
  entryMode: state.entryMode,
  copyGenerationMode: state.copyGenerationMode,
  adFormat: state.selectedChannelId,
  runMode: resolveGenerationRunMode(engine),
  selectedReferenceTemplateId,
  metadata: {
    source: "web_generation_flow",
    selected_engine: engine,
    requested_engine: backendEngine,
    t2i_engine: backendEngine,
    selected_engine_label: engineOption.modelName,
    selected_copy_id: state.selectedCopyId || null,
    selected_channel_id: state.selectedChannelId,
    selected_tone: state.selectedTone || null,
    reference_template_title: state.selectedReferenceTemplateTitle || null
  }
});
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(web): send final generation jobs to graph"
```

---

### Task 3: Backend Engine Preference Normalization

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Modify: `orchestrator/app/chat_threads/state_snapshot.py`
- Test: `orchestrator/tests/test_generation_job_service.py`

- [ ] **Step 1: Write the failing test**

Add this test to `orchestrator/tests/test_generation_job_service.py`:

```python
def test_graph_immediate_snapshot_preserves_selected_engine():
    from orchestrator.app.chat_threads.state_service import get_chat_state_snapshot_by_key

    request = GenerationJobCreateRequest(
        user_input="카페 신메뉴 광고 만들어줘",
        run_mode="graph_immediate",
        metadata={
            "selected_engine": "flux_schnell",
            "requested_engine": "flux",
            "t2i_engine": "flux",
        },
    )

    job = create_generation_job(request)
    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:input",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )

    assert snapshot is not None
    assert job.metadata["engine_preference"] == "flux"
    assert job.metadata["t2i_engine"] == "flux"
    assert snapshot.state_payload["engine"] == "flux"
    assert snapshot.state_payload["current_brief"]["requested_engine"] == "flux"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_service.py::test_graph_immediate_snapshot_preserves_selected_engine -q
```

Expected: FAIL because `graph_immediate` currently has no engine preference and the input snapshot lacks `engine`.

- [ ] **Step 3: Add engine normalization helpers**

In `orchestrator/app/chat_threads/state_snapshot.py`, add `engine` to `PERSISTENT_FIELDS`:

```python
    "ad_format",
    "engine",
    "copy_generation_mode",
```

In `orchestrator/app/generation_jobs/service.py`, replace `_engine_preference()` with this helper block:

```python
def _normalize_engine_preference(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "gpt_image_2": "gpt_image_2",
        "gptimage2": "gpt_image_2",
        "gpt_image2": "gpt_image_2",
        "flux": "flux",
        "flux_schnell": "flux",
        "flux_1_schnell": "flux",
        "sd35": "sd35_large",
        "sd35_large": "sd35_large",
        "sd3_5_large": "sd35_large",
    }
    return aliases.get(normalized)


def _engine_preference(run_mode: str) -> str | None:
    if run_mode in {"gpt_image_2_actual", "gpt_image_2_smoke"}:
        return "gpt_image_2"
    if run_mode in {"sd35_local", "sd35_local_smoke", "sd35_large_real"}:
        return "sd35_large"
    if run_mode in {"flux_local", "flux_local_smoke", "flux_schnell_real", "flux", "flux_smoke"}:
        return "flux"
    return None


def _engine_preference_for_request(request: GenerationJobCreateRequest) -> str | None:
    metadata = request.metadata or {}
    for key in ("requested_engine", "t2i_engine", "selected_engine", "engine"):
        engine = _normalize_engine_preference(metadata.get(key))
        if engine:
            return engine
    return _engine_preference(request.run_mode)


def _apply_generation_engine_to_state(restored_payload: dict, request: GenerationJobCreateRequest) -> None:
    engine = _engine_preference_for_request(request)
    if not engine:
        return
    restored_payload["engine"] = engine
    current_brief = restored_payload.setdefault("current_brief", {})
    if isinstance(current_brief, dict):
        current_brief["requested_engine"] = engine
        current_brief["engine"] = engine
```

- [ ] **Step 4: Use the request-aware helper in memory job creation**

Inside `_create_generation_job_memory()`, after `restored_payload = state_service.restore_thread_state(...)`, add:

```python
        _apply_generation_engine_to_state(restored_payload, request)
```

In the same function, before building `job = GenerationJobResponse(...)`, add:

```python
        engine_preference = _engine_preference_for_request(request)
```

Replace:

```python
"engine_preference": _engine_preference(request.run_mode),
"t2i_engine": _engine_preference(request.run_mode),
```

with:

```python
"engine_preference": engine_preference,
"t2i_engine": engine_preference,
```

- [ ] **Step 5: Use the request-aware helper in DB job creation**

Inside `_create_generation_job_db()`, before the metadata dict is created, add:

```python
        engine_preference = _engine_preference_for_request(request)
```

Replace metadata fields:

```python
"engine_preference": _engine_preference(request.run_mode),
"t2i_engine": _engine_preference(request.run_mode),
```

with:

```python
"engine_preference": engine_preference,
"t2i_engine": engine_preference,
```

Replace repository call args:

```python
engine=_engine_preference(request.run_mode),
model_name=_model_name_for_run_mode(request.run_mode),
```

with:

```python
engine=engine_preference,
model_name=engine_preference,
```

After the DB `restored_payload = state_service.restore_thread_state(...)` call, add:

```python
        _apply_generation_engine_to_state(restored_payload, request)
```

- [ ] **Step 6: Run the test to verify it passes**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_service.py::test_graph_immediate_snapshot_preserves_selected_engine -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add orchestrator/app/generation_jobs/service.py orchestrator/tests/test_generation_job_service.py
git commit -m "feat(orchestrator): persist graph generation engine preference"
```

---

### Task 4: Graph Executor Receives Selected Engine

**Files:**
- Modify: `orchestrator/tests/test_generation_job_graph_execution.py`

- [ ] **Step 1: Write the failing test**

Add this test to `orchestrator/tests/test_generation_job_graph_execution.py`:

```python
def test_execute_generation_job_graph_receives_selected_engine(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/graph-engine.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/graph-engine.png"
            return state

    monkeypatch.setattr("orchestrator.app.graph.builder.build_marketing_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="정교한 베이커리 광고 만들어줘",
        run_mode="graph_immediate",
        metadata={
            "selected_engine": "sd35_large",
            "requested_engine": "sd35_large",
            "t2i_engine": "sd35_large",
        },
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["engine"] == "sd35_large"
    assert received_payload["current_brief"]["requested_engine"] == "sd35_large"
```

- [ ] **Step 2: Run the test to verify it passes after Task 3**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_graph_execution.py::test_execute_generation_job_graph_receives_selected_engine -q
```

Expected: PASS. If it fails, the graph executor is not restoring the updated input snapshot.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tests/test_generation_job_graph_execution.py
git commit -m "test(orchestrator): prove graph executor receives selected engine"
```

---

### Task 5: Generation Job Router Uses Graph Executor

**Files:**
- Modify: `orchestrator/tests/test_api_generation_jobs_router.py`

- [ ] **Step 1: Write the failing test**

Add this test to `orchestrator/tests/test_api_generation_jobs_router.py`:

```python
def test_graph_immediate_routes_to_graph_executor_with_engine_metadata(client, monkeypatch):
    captured = {}

    def fake_execute_generation_job_graph(job_id, request):
        from orchestrator.app.generation_jobs.service import get_generation_job

        captured["job_id"] = job_id
        captured["run_mode"] = request.run_mode
        captured["metadata"] = request.metadata
        job = get_generation_job(job_id)
        assert job is not None
        return job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.execute_generation_job_graph",
        fake_execute_generation_job_graph,
    )

    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_immediate",
            "metadata": {
                "selected_engine": "flux_schnell",
                "requested_engine": "flux",
                "t2i_engine": "flux",
            },
        },
    )

    assert response.status_code == 201
    assert captured["run_mode"] == "graph_immediate"
    assert captured["metadata"]["selected_engine"] == "flux_schnell"
    assert captured["metadata"]["requested_engine"] == "flux"
    assert captured["metadata"]["t2i_engine"] == "flux"
```

- [ ] **Step 2: Run the test**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py::test_graph_immediate_routes_to_graph_executor_with_engine_metadata -q
```

Expected: PASS. The route already has a graph branch; this test protects it from future regression.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/tests/test_api_generation_jobs_router.py
git commit -m "test(orchestrator): lock graph immediate router path"
```

---

### Task 6: UI-Orchestrator Coverage Matrix

**Files:**
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.ts`
- Test: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`

- [ ] **Step 1: Write the failing test**

In `apps/web/lib/ui-orchestrator-route-coverage.test.ts`, replace the test named `"makes the current final generation gap explicit"` with:

```ts
it("marks final generation as a full LangGraph generation job flow", () => {
  const report = buildUiOrchestratorRouteCoverageReport();
  const row = findUiOrchestratorRouteCoverageRow(report, "final-model-generation");

  expect(row?.connected).toBe(true);
  expect(row?.executionMode).toBe("generation-job-graph");
  expect(row?.apiCalls).toEqual(["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"]);
  expect(row?.fullGraphExecution).toBe(true);
  expect(row?.graphNodesReached).toEqual(
    expect.arrayContaining([
      "format_planner",
      "tone_binding",
      "copy_spec_parser",
      "image_prompt_planner",
      "prompt_renderer",
      "t2i_request_builder",
      "t2i_generation",
      "background_validation",
      "safe_area_gate",
      "readability_gate",
      "final_validation",
      "result"
    ])
  );
  expect(row?.graphNodesBypassed).toEqual([]);
});
```

Replace the test named `"does not claim any current UI route fully executes the final marketing graph"` with:

```ts
it("claims final generation as the current full graph route", () => {
  const report = buildUiOrchestratorRouteCoverageReport();

  expect(report.fullGraphIds).toEqual(["final-model-generation"]);
  expect(report.fullGraphCount).toBe(1);
  expect(report.directT2iIds).toEqual([]);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
npm test -- --run lib/ui-orchestrator-route-coverage.test.ts
```

Expected: FAIL because the matrix still says `generation-job-direct-t2i`.

- [ ] **Step 3: Update the matrix**

In `apps/web/lib/ui-orchestrator-route-coverage.ts`, replace the `final-model-generation` row with:

```ts
{
  id: "final-model-generation",
  label: "모델 선택 최종 이미지 생성",
  userFlow: "GPT-image-2, FLUX.1-schnell, SD3.5 Large 중 하나를 선택해 최종 생성",
  uiEntryPoints: ["GenerationEngineSelector", "BriefConfirmStep", "GenerationInProgressStep", "GenerationCompleteStep"],
  apiCalls: ["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"],
  executionMode: "generation-job-graph",
  connected: true,
  fullGraphExecution: true,
  graphNodesReached: FINAL_GENERATION_GRAPH_CHAIN,
  graphNodesBypassed: [],
  notes: "현재 UI의 모델 선택은 graph_immediate generation job으로 전달되며, 선택 엔진은 graph state의 engine preference로 t2i_generation 노드까지 전달된다."
}
```

Update the `reference-template-selection` row note to:

```ts
notes: "템플릿 id는 graph 시작과 final graph generation job에 전달되며, 최종 이미지 생성의 style hint로 이어진다."
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
npm test -- --run lib/ui-orchestrator-route-coverage.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/ui-orchestrator-route-coverage.ts apps/web/lib/ui-orchestrator-route-coverage.test.ts
git commit -m "test(web): mark final generation as graph covered"
```

---

### Task 7: Full Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run targeted web tests**

Run:

```bash
npm test -- --run lib/generation-engine.test.ts app/generate/chat/ChatGenerateClient.test.tsx lib/ui-orchestrator-route-coverage.test.ts
```

Expected: PASS. Existing React `act(...)` warnings may appear if they already existed; no new failures.

- [ ] **Step 2: Run targeted orchestrator tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_generation_job_service.py orchestrator/tests/test_generation_job_graph_execution.py orchestrator/tests/test_api_generation_jobs_router.py -q
```

Expected: PASS.

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Commit verification-only updates if any**

If no files changed during verification, skip this commit. If test snapshots or docs changed, commit only those files:

```bash
git add <changed-test-or-doc-files>
git commit -m "test: verify final generation graph route"
```

---

## Rollback Notes

If the graph path fails in a deployed environment, revert only the UI payload change from Task 2. The backend direct T2I run modes remain intact through `resolveDirectGenerationRunMode()` and the existing generation job router branches.

## Expected End State

- UI final generation calls `POST /api/generation-jobs` with `runMode: "graph_immediate"`.
- UI still records the selected model as `selected_engine`.
- Backend normalizes:
  - `gpt_image_2` -> `gpt_image_2`
  - `flux_schnell` -> `flux`
  - `sd35_large` -> `sd35_large`
- Input snapshots contain `state_payload["engine"]`.
- `execute_generation_job_graph()` restores the snapshot and invokes the full marketing graph.
- The coverage matrix reports `final-model-generation` as `generation-job-graph`.

## Self-Review

- Spec coverage: The plan covers frontend payload changes, backend state propagation, router protection, graph executor proof, and coverage diagnostics.
- Placeholder scan: No unfinished markers or open-ended implementation placeholders remain.
- Type consistency: UI engine IDs, backend engine names, and `graph_immediate` run mode are consistently named across tasks.
