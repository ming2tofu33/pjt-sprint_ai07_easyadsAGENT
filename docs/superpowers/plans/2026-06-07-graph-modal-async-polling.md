# Graph Modal Async Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let FLUX/SD generation inside `graph_job` submit Modal work asynchronously, persist the Modal call id, and complete through job polling.

**Architecture:** The graph T2I node submits Modal and returns `modal_running` instead of waiting for image bytes. GenerationJob execution stores the graph state snapshot and Modal call id, then `GET /generation-jobs/{job_id}` polls Modal, writes the returned image, runs the remaining validation/render/result nodes, and marks the job done.

**Tech Stack:** FastAPI GenerationJob APIs, LangGraph state snapshots, Modal SDK wrapper, existing TLFP graph node functions.

---

### Task 1: Graph Modal Submit Boundary

**Files:**
- Modify: `orchestrator/app/t2i/graph_engines.py`
- Modify: `orchestrator/app/llm/nodes/t2i_generation.py`
- Modify: `orchestrator/app/graph/routers.py`
- Modify: `orchestrator/app/graph/builder.py`

- [x] Change Modal graph engine to submit Modal and return `T2IResult` metadata with `modal_status=submitted`.
- [x] Change `t2i_generation_node` to return `status=modal_running` when a Modal call id is present without image paths.
- [x] Route `t2i_generation` to `END` for `modal_running` or `failed`; otherwise continue to `background_validation`.

### Task 2: Job Persistence

**Files:**
- Modify: `orchestrator/app/generation_jobs/service.py`
- Modify: `orchestrator/app/generation_jobs/execution.py`

- [x] Add a service helper to mark a GenerationJob as `running/modal_running` and persist `modal_call_id`.
- [x] When graph execution returns `modal_running`, save a `graph_modal_pending` snapshot and call the helper.

### Task 3: Poll Completion

**Files:**
- Modify: `orchestrator/app/generation_jobs/execution.py`
- Modify: `orchestrator/app/generation_jobs/service.py`

- [x] Add a graph Modal polling function that polls Modal, writes the image into the graph output dir, injects a `t2i_result`, runs downstream TLFP nodes, and marks the job done.
- [x] Make `maybe_poll_generation_job_from_modal()` use the graph Modal poller for graph jobs with `graph_modal_pending`.

### Task 4: Tests

**Files:**
- Modify: `orchestrator/tests/test_t2i_service.py`
- Modify: `orchestrator/tests/test_generation_job_graph_execution.py`
- Modify: `orchestrator/tests/test_generation_job_modal_execution.py`

- [x] Update Modal graph engine tests for submit-only behavior.
- [x] Add graph execution test for `modal_running` persistence.
- [x] Add polling test for graph Modal completion.
