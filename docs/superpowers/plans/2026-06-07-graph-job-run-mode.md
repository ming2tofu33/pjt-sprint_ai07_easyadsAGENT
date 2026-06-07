# Graph Job Run Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the confusing `graph_immediate` generation mode with a job-tracked `graph_job` flow.

**Architecture:** UI sends `runMode: "graph_job"` for normal graph generation. The API creates a GenerationJob and schedules graph execution as a background task, while the UI polls the job state and handles `waiting_user_input`, `running`, `done`, and `failed` through the existing job API.

**Tech Stack:** Next.js/Vitest frontend, FastAPI/Pydantic backend, in-process GenerationJob service, LangGraph execution bridge.

---

### Task 1: Backend Run Mode Contract

**Files:**
- Modify: `orchestrator/app/api/schemas/generation_jobs.py`
- Modify: `orchestrator/app/generation_jobs/service.py`
- Modify: `orchestrator/app/generation_jobs/execution.py`

- [x] Add `graph_job` to the API run mode literal and remove `graph_immediate`.
- [x] Make initial job metadata use `requested_run_mode=graph_job`, `effective_run_mode=graph_job`, and `execution_mode=pending_graph_execution`.
- [x] Make graph completion/resume metadata report `graph_job`, not `graph_immediate`.

### Task 2: Backend Route Execution

**Files:**
- Modify: `orchestrator/app/api/routers/generation_jobs.py`
- Modify: `orchestrator/app/generation_jobs/execution.py`
- Test: `orchestrator/tests/test_api_generation_jobs_router.py`

- [x] Inject `BackgroundTasks` into the create route.
- [x] For `graph_job`, return the created job immediately and schedule `execute_generation_job_graph(job_id, request)` in the background.
- [x] For graph answers, return a running job immediately and schedule `resume_generation_job_graph(job_id, answer)` in the background.
- [x] Remove the `graph_immediate` route branch.
- [x] Update API tests to assert `graph_job` metadata and background scheduling.

### Task 3: Frontend Run Mode

**Files:**
- Modify: `apps/web/lib/generation-engine.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/lib/ui-orchestrator-route-coverage.ts`
- Test: `apps/web/lib/generation-engine.test.ts`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [x] Make `resolveGenerationRunMode()` return `graph_job`.
- [x] Replace remaining hardcoded `graph_immediate` payloads with `graph_job`.
- [x] Update tests to expect `graph_job`.

### Task 4: Verification

**Commands:**
- [x] `uv run python -m pytest orchestrator/tests/test_api_generation_jobs_router.py orchestrator/tests/test_generation_job_execution_bridge.py orchestrator/tests/test_generation_job_service.py orchestrator/tests/test_generation_job_graph_execution.py -q`
- [x] `cd apps/web && npm test -- --run lib/generation-engine.test.ts app/generate/chat/ChatGenerateClient.test.tsx`
- [x] `cd apps/web && npx tsc --noEmit`

**Expected:** Backend and frontend tests pass. Existing React `act(...)` warnings may still appear in the chat component test suite.
