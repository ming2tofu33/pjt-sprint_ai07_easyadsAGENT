# UI Orchestrator Route Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add code and tests that show which UI generation flows are connected to LangGraph, direct T2I jobs, or still missing UI coverage.

**Architecture:** Keep the existing capability coverage matrix intact, and add a second route-level diagnostic matrix for actual UI → API → orchestrator execution paths. Tests should make the current limitation explicit: context/brief flows use LangGraph, while final model-selected image generation currently uses direct T2I generation jobs and bypasses the full graph validation/result chain.

**Tech Stack:** TypeScript utility module, Vitest unit tests, existing Next.js frontend test setup.

---

## Tasks

### Task 1: Add Route Coverage Diagnostics

**Files:**
- Create: `apps/web/lib/ui-orchestrator-route-coverage.ts`
- Test: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`

- [ ] Define route execution modes:
  - `langgraph-interrupt-loop`
  - `langgraph-resume`
  - `generation-job-direct-t2i`
  - `generation-job-graph`
  - `ui-only`
- [ ] Define current route rows:
  - `context-question-loop`
  - `brief-confirmation`
  - `final-model-generation`
  - `reference-template-selection`
  - `reference-image-upload`
  - `validation-feedback`
- [ ] Include `apiCalls`, `graphNodesReached`, `graphNodesBypassed`, `connected`, and `fullGraphExecution`.
- [ ] Export report helpers to list connected, full-graph, direct-T2I, and missing rows.

### Task 2: Test Current Architecture Truthfully

**Files:**
- Test: `apps/web/lib/ui-orchestrator-route-coverage.test.ts`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] Assert context question loop is connected through `chat/start` and `chat/answer`.
- [ ] Assert brief confirmation is connected through `chat/brief`.
- [ ] Assert final model generation is connected but **not** full graph execution.
- [ ] Assert final model generation bypasses validation/result graph nodes for now.
- [ ] Assert ChatGenerateClient sends `flux_schnell_real`/`gpt_image_2_actual`, not `graph_immediate`, until the full graph handoff is intentionally implemented.

### Task 3: Verify

**Files:**
- Existing tests

- [ ] Run:
  - `npm test -- --run lib/ui-orchestrator-route-coverage.test.ts lib/ui-graph-coverage.test.ts app/generate/chat/ChatGenerateClient.test.tsx`
  - `npx tsc --noEmit`
