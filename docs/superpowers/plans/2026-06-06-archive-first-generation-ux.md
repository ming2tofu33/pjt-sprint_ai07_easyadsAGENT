# Archive-First Generation UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve LangGraph chat context across UI restores and change the result UX so generated images are checked from the archive, not rendered immediately from backend-local file paths.

**Architecture:** Treat image generation as an asynchronous job whose browser-visible artifact is the archive item, not the raw job output. The backend must restore thread snapshots from the workspace that owns the thread, and the frontend must map persisted LangGraph snake_case state into the existing camelCase chat reducer state. Completion UI must stop converting `data/outputs/...` into image previews, because those files live on the orchestrator/Railway filesystem and are not readable from the Vercel/web filesystem.

**Tech Stack:** FastAPI, Pydantic, Postgres repositories, LangGraph job snapshots, Next.js App Router, React reducer state, Vitest, Testing Library, Cloudflare R2 public/signed result URLs.

---

## Problem Summary

Two user-visible bugs are linked to the current generation contract:

1. The chat flow loses or resets user-provided context after `graph_immediate` creates a thread. The UI fetches `/chat-threads/{threadId}/state`, dispatches `reset`, then reads fields such as `payload.context` and `payload.copyCandidates`. The persisted graph state actually stores fields such as `user_input`, `business_type`, `item_or_service`, `promotion_goal`, `copy_generation_mode`, and `pending_interrupt`.
2. The complete screen shows a broken image because `data/outputs/...` is transformed into `/api/generated-assets?...`. That route reads files from the web server filesystem, while production generation files are created on the orchestrator server. A browser-safe image must come from a URL field such as `final_image_url`, `preview_image_url`, `download_url`, or an archive item backed by R2.

The desired UX is archive-first:

- If the job is queued/running/waiting, tell the user the result will be available in the archive.
- If the job is done, tell the user the image is ready to check in the archive.
- If the job only has local artifact paths, do not show a fake or broken preview.
- The archive page remains the place that shows generated images and downloads, but only when a browser-safe URL exists.

## File Structure

### Backend State Restore

- Modify `orchestrator/app/chat_threads/service.py`
  - Add `get_chat_thread_with_workspace(thread_id, user_id=None)`.
  - Return both the `ChatThreadResponse` and the row's owning `workspace_id`.
  - Keep `get_chat_thread()` behavior unchanged.

- Modify `orchestrator/app/api/routers/chat_threads.py`
  - Make `/api/v1/chat-threads/{thread_id}/state` call `get_chat_thread_with_workspace()`.
  - Pass the owning `workspace_id` into `state_service.get_latest_thread_state_snapshot()`.

- Modify `orchestrator/tests/test_chat_thread_service.py`
  - Add a unit regression for workspace fallback when a thread was created under a different demo workspace.

- Modify `orchestrator/tests/test_multiturn_state_api.py`
  - Add a route regression proving snapshot lookup receives the actual thread workspace.

### Frontend State Restore

- Create `apps/web/lib/chat-thread-state-mapper.ts`
  - Convert `ChatStateSnapshotResponse` into a reducer restore payload.
  - Normalize snake_case/camelCase graph fields.
  - Extract pending option questions from `pending_interrupt.option_question`.

- Create `apps/web/lib/chat-thread-state-mapper.test.ts`
  - Cover user input, inferred context, custom copy fields, copy generation mode, selected channel, selected engine, and pending question extraction.

- Modify `apps/web/types/marketing.ts`
  - Add a `restoreThreadSnapshot` action with explicit fields.

- Modify `apps/web/lib/chat-flow.ts`
  - Implement `restoreThreadSnapshot`.
  - Restore conversation messages without clearing the user's prompt.

- Modify `apps/web/lib/chat-flow.test.ts`
  - Add reducer regression for restored state.

- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Use the mapper in the `threadIdParam` restore effect.
  - Do not dispatch `reset` before restoring a snapshot.
  - If snapshot fetch fails, show toast and leave current in-memory state alone.

### Archive-First Result UX

- Modify `apps/web/lib/generation-result-utils.ts`
  - Stop converting backend-local artifact paths into display/download URLs.
  - Keep `hasOnlyLocalArtifactPath()` so the UI can explain why no direct preview is shown.

- Modify `apps/web/lib/generation-result-utils.test.ts`
  - Update local-path-only expectations to return `null` display/download URLs.

- Modify `apps/web/components/generate/GenerationCompleteStep.tsx`
  - Remove direct generated image card rendering from the completion screen.
  - Show status-specific archive guidance.
  - Add primary CTA `보관함에서 확인하기`.

- Create `apps/web/components/generate/GenerationCompleteStep.test.tsx`
  - Verify no `<img>` is rendered for local-only artifact paths.
  - Verify archive CTA fires.

- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Pass `onOpenArchive={() => navigateTo("ads")}`.
  - Remove completion-screen save/edit dependencies.

---

## Task 1: Backend Service Returns Thread And Owning Workspace

**Files:**
- Modify: `orchestrator/app/chat_threads/service.py`
- Modify: `orchestrator/tests/test_chat_thread_service.py`

- [ ] **Step 1: Write the failing service test**

Append this test to `orchestrator/tests/test_chat_thread_service.py`:

```python
def test_get_chat_thread_with_workspace_falls_back_to_owning_workspace(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(chat_service, "_get_demo_workspace_id", lambda user_id=None: "workspace_demo")

    calls = []

    def fake_get_chat_thread_by_public_id(public_thread_id, workspace_id=None, connection=None, for_update=False):
        calls.append(workspace_id)
        if workspace_id == "workspace_demo":
            return None
        return {
            "id": "internal_thread_uuid",
            "public_thread_id": public_thread_id,
            "workspace_id": "workspace_actual",
            "title": "카페 신메뉴 광고",
            "status": "generating",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_job_id": None,
            "active_public_job_id": None,
            "final_output_id": None,
            "last_message_at": "2026-06-06T00:00:00+00:00",
            "archived_at": None,
            "created_at": "2026-06-06T00:00:00+00:00",
            "updated_at": "2026-06-06T00:00:00+00:00",
        }

    monkeypatch.setattr(chat_service.chat_thread_repo, "get_chat_thread_by_public_id", fake_get_chat_thread_by_public_id)

    result = chat_service.get_chat_thread_with_workspace("thread_generated")

    assert result is not None
    thread, workspace_id = result
    assert thread.thread_id == "thread_generated"
    assert workspace_id == "workspace_actual"
    assert calls == ["workspace_demo", None]
```

- [ ] **Step 2: Run the single failing test**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_chat_thread_service.py::test_get_chat_thread_with_workspace_falls_back_to_owning_workspace -q
```

Expected: fail with `AttributeError` because `get_chat_thread_with_workspace` is not defined.

- [ ] **Step 3: Add the service helper**

Add this function immediately below `_get_chat_thread_db()` in `orchestrator/app/chat_threads/service.py`:

```python
def get_chat_thread_with_workspace(
    thread_id: str,
    user_id: str | None = None,
) -> tuple[ChatThreadResponse, str] | None:
    if not _use_postgres():
        thread = get_chat_thread(thread_id, user_id=user_id)
        return (thread, "memory_workspace") if thread else None

    workspace_id = _get_demo_workspace_id(user_id)
    row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=workspace_id)

    if not row and user_id is None:
        row = chat_thread_repo.get_chat_thread_by_public_id(thread_id, workspace_id=None)

    if not row:
        return None

    return _thread_row_to_response(row), str(row["workspace_id"])
```

- [ ] **Step 4: Run the service test**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_chat_thread_service.py::test_get_chat_thread_with_workspace_falls_back_to_owning_workspace -q
```

Expected: pass.

- [ ] **Step 5: Commit the service change**

Run:

```bash
git add orchestrator/app/chat_threads/service.py orchestrator/tests/test_chat_thread_service.py
git commit -m "fix(orchestrator): resolve chat thread owning workspace"
```

---

## Task 2: State Route Reads Snapshots From Owning Workspace

**Files:**
- Modify: `orchestrator/app/api/routers/chat_threads.py`
- Modify: `orchestrator/tests/test_multiturn_state_api.py`

- [ ] **Step 1: Update the existing success test**

In `orchestrator/tests/test_multiturn_state_api.py`, replace `test_get_chat_thread_state_success` with:

```python
def test_get_chat_thread_state_success(client, monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service
    from orchestrator.app.chat_threads import state_service
    from orchestrator.app.api.schemas.chat_threads import ChatThreadResponse
    from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse

    captured = {}
    thread = ChatThreadResponse(
        thread_id="thread_1",
        title="카페 광고",
        status="generating",
        final_brief={},
        active_job_id=None,
        has_final_output=False,
        last_message_at="2026-06-06T00:00:00+00:00",
        created_at="2026-06-06T00:00:00+00:00",
        updated_at="2026-06-06T00:00:00+00:00",
    )
    mock_snapshot = ChatStateSnapshotResponse(
        snapshot_id="snap_1",
        thread_id="thread_1",
        job_id="job_1",
        snapshot_version=1,
        schema_version=1,
        snapshot_kind="input",
        state_payload={"test": "payload"},
        changed_fields=[],
        created_at="2026-06-06T00:00:00+00:00",
    )

    monkeypatch.setattr(chat_service, "get_chat_thread_with_workspace", lambda thread_id, user_id=None: (thread, "workspace_actual"))

    def fake_get_latest_thread_state_snapshot(**kwargs):
        captured.update(kwargs)
        return mock_snapshot

    monkeypatch.setattr(state_service, "get_latest_thread_state_snapshot", fake_get_latest_thread_state_snapshot)

    response = client.get("/api/v1/chat-threads/thread_1/state")

    assert response.status_code == 200
    assert response.json()["snapshot"]["snapshot_id"] == "snap_1"
    assert response.json()["snapshot"]["state_payload"]["test"] == "payload"
    assert captured["public_thread_id"] == "thread_1"
    assert captured["workspace_id"] == "workspace_actual"
```

- [ ] **Step 2: Run the failing route test**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_multiturn_state_api.py::test_get_chat_thread_state_success -q
```

Expected: fail because the route still calls `get_chat_thread()` and `_get_demo_workspace()`.

- [ ] **Step 3: Replace the route implementation**

In `orchestrator/app/api/routers/chat_threads.py`, replace `get_chat_thread_state_route()` with:

```python
def get_chat_thread_state_route(
    thread_id: str,
    user_id: str | None = Query(default=None, alias="userId"),
) -> ChatThreadStateGetResponse:
    resolved = chat_service.get_chat_thread_with_workspace(thread_id, user_id=user_id)
    if not resolved:
        _not_found(thread_id)

    _thread, workspace_id = resolved
    snapshot = state_service.get_latest_thread_state_snapshot(
        public_thread_id=thread_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return ChatThreadStateGetResponse(snapshot=snapshot)
```

- [ ] **Step 4: Run backend route tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_multiturn_state_api.py orchestrator/tests/test_chat_thread_service.py -q
```

Expected: pass.

- [ ] **Step 5: Run a local DB smoke check**

Run:

```bash
set -a
source .env
set +a
EASYADS_DB_BACKEND=postgres uv run python - <<'PY'
from fastapi.testclient import TestClient
from orchestrator.app.main import app

client = TestClient(app)
created = client.post("/api/v1/generation-jobs", json={
    "userInput": "카페 신메뉴 광고 만들어줘",
    "runMode": "graph_immediate"
}).json()["job"]

state = client.get(f"/api/v1/chat-threads/{created['thread_id']}/state")
print(created["status"], created["thread_id"], state.status_code)
print(state.text[:500])
PY
```

Expected: printed status code is `200`.

- [ ] **Step 6: Commit the route change**

Run:

```bash
git add orchestrator/app/api/routers/chat_threads.py orchestrator/tests/test_multiturn_state_api.py
git commit -m "fix(orchestrator): restore graph snapshots from thread workspace"
```

---

## Task 3: Add A Mapper For Persisted LangGraph State

**Files:**
- Create: `apps/web/lib/chat-thread-state-mapper.ts`
- Create: `apps/web/lib/chat-thread-state-mapper.test.ts`

- [ ] **Step 1: Write mapper tests**

Create `apps/web/lib/chat-thread-state-mapper.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { mapChatThreadSnapshotToRestoreState } from "./chat-thread-state-mapper";

describe("mapChatThreadSnapshotToRestoreState", () => {
  it("maps snake_case graph state into UI restore fields", () => {
    const restore = mapChatThreadSnapshotToRestoreState({
      snapshot_id: "snapshot_1",
      thread_id: "thread_1",
      job_id: "job_1",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "input",
      state_payload: {
        user_input: "오늘 저녁 카페 딸기라떼 할인 광고",
        business_type: "카페",
        item_or_service: "딸기라떼",
        promotion_goal: "할인 이벤트",
        copy_generation_mode: "custom_input",
        user_custom_headline: "오늘만 딸기라떼 반값",
        user_custom_subcopy: "오후 2시부터 5시까지",
        selected_channel_id: "instagram-feed",
        selected_tone: "상큼한",
        image_generation_engine: "gpt_image_2"
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    });

    expect(restore).toMatchObject({
      prompt: "오늘 저녁 카페 딸기라떼 할인 광고",
      jobId: "job_1",
      threadId: "thread_1",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "할인 이벤트"
      },
      copyGenerationMode: "custom_input",
      selectedChannelId: "instagram-feed",
      selectedTone: "상큼한",
      selectedImageGenerationEngine: "gpt_image_2",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
    });
  });

  it("extracts a pending option question from a waiting snapshot", () => {
    const restore = mapChatThreadSnapshotToRestoreState({
      snapshot_id: "snapshot_waiting",
      thread_id: "thread_waiting",
      job_id: "job_waiting",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "waiting_user_input",
      state_payload: {
        user_input: "광고 만들어줘",
        business_type: "카페",
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "item_or_service",
            question: "홍보할 상품이나 서비스는 무엇인가요?",
            options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
          }
        }
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    });

    expect(restore?.generationJob.status).toBe("waiting_user_input");
    expect(restore?.currentQuestion?.field).toBe("item_or_service");
    expect(restore?.currentQuestion?.question).toBe("홍보할 상품이나 서비스는 무엇인가요?");
    expect(restore?.conversationMessages).toEqual([
      { role: "user", text: "광고 만들어줘" },
      { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
    ]);
  });
});
```

- [ ] **Step 2: Run mapper tests and verify failure**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts
```

Expected: fail because `apps/web/lib/chat-thread-state-mapper.ts` does not exist.

- [ ] **Step 3: Create the mapper**

Create `apps/web/lib/chat-thread-state-mapper.ts`:

```ts
import type { ChatFlowState, CopyGenerationMode, InferredContext, OptionQuestion } from "@/types/marketing";
import type { ChatStateSnapshotResponse, GenerationJob } from "./api-client";
import { DEFAULT_IMAGE_GENERATION_ENGINE, type ImageGenerationEngine } from "./generation-engine";

export type ThreadSnapshotRestoreState = {
  prompt: string;
  jobId: string;
  threadId: string;
  context: InferredContext;
  copyGenerationMode: CopyGenerationMode;
  selectedChannelId: string;
  selectedTone: string;
  selectedImageGenerationEngine: ImageGenerationEngine;
  customDirection: string;
  userCustomHeadline: string;
  userCustomSubcopy: string;
  sourceImagePath: string | null;
  referenceImagePath: string | null;
  selectedReferenceTemplateId: string | null;
  selectedReferenceTemplateTitle: string | null;
  generationJob: GenerationJob;
  currentQuestion: OptionQuestion | null;
  conversationMessages: ChatFlowState["conversationMessages"];
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    const normalized = stringValue(value);
    if (normalized) {
      return normalized;
    }
  }
  return "";
}

function copyMode(value: unknown): CopyGenerationMode {
  const mode = stringValue(value);
  if (mode === "suggest_candidates" || mode === "auto_pilot" || mode === "custom_input" || mode === "no_copy") {
    return mode;
  }
  return "suggest_candidates";
}

function imageEngine(value: unknown): ImageGenerationEngine {
  const engine = stringValue(value);
  if (engine === "gpt_image_2" || engine === "flux_schnell" || engine === "sd35_large") {
    return engine;
  }
  return DEFAULT_IMAGE_GENERATION_ENGINE;
}

function optionQuestionFrom(value: unknown): OptionQuestion | null {
  const question = asRecord(value);
  const field = stringValue(question.field);
  const text = stringValue(question.question);
  const options = Array.isArray(question.options) ? question.options : [];
  if (!field || !text) {
    return null;
  }
  return {
    field,
    question: text,
    options: options as OptionQuestion["options"],
    required: typeof question.required === "boolean" ? question.required : undefined,
    multi_select: typeof question.multi_select === "boolean" ? question.multi_select : undefined
  };
}

function extractQuestion(payload: Record<string, unknown>, metadata: Record<string, unknown>): OptionQuestion | null {
  const payloadInterrupt = asRecord(payload.pending_interrupt);
  const metadataInterrupt = asRecord(metadata.pending_interrupt);
  return (
    optionQuestionFrom(payload.option_question) ??
    optionQuestionFrom(payload.question) ??
    optionQuestionFrom(payloadInterrupt.option_question) ??
    optionQuestionFrom(metadataInterrupt.option_question)
  );
}

export function mapChatThreadSnapshotToRestoreState(snapshot: ChatStateSnapshotResponse | null | undefined): ThreadSnapshotRestoreState | null {
  if (!snapshot) {
    return null;
  }

  const payload = asRecord(snapshot.state_payload);
  const metadata = asRecord(snapshot.metadata);
  const currentBrief = asRecord(payload.current_brief);
  const prompt = firstString(payload.user_input, payload.prompt, metadata.user_input_preview);
  const threadId = firstString(snapshot.thread_id, payload.thread_id);
  const jobId = firstString(snapshot.job_id, payload.job_id);
  if (!threadId) {
    return null;
  }

  const currentQuestion = extractQuestion(payload, metadata);
  const status = snapshot.snapshot_kind === "waiting_user_input" || currentQuestion ? "waiting_user_input" : "queued";
  const context = {
    businessType: firstString(payload.business_type, payload.businessType, currentBrief.business_type, currentBrief.businessType),
    itemOrService: firstString(payload.item_or_service, payload.itemOrService, currentBrief.item_or_service, currentBrief.itemOrService),
    promotionGoal: firstString(payload.promotion_goal, payload.promotionGoal, currentBrief.promotion_goal, currentBrief.promotionGoal)
  };

  const conversationMessages: ChatFlowState["conversationMessages"] = [];
  if (prompt) {
    conversationMessages.push({ role: "user", text: prompt });
  }
  if (currentQuestion) {
    conversationMessages.push({ role: "assistant", text: currentQuestion.question });
  }

  return {
    prompt,
    jobId,
    threadId,
    context,
    copyGenerationMode: copyMode(payload.copy_generation_mode ?? payload.copyGenerationMode),
    selectedChannelId: firstString(payload.selected_channel_id, payload.selectedChannelId, payload.ad_format) || "instagram-feed",
    selectedTone: firstString(payload.selected_tone, payload.selectedTone) || "감성적인",
    selectedImageGenerationEngine: imageEngine(payload.image_generation_engine ?? payload.selected_image_generation_engine ?? payload.selectedImageGenerationEngine),
    customDirection: firstString(payload.custom_direction, payload.customDirection),
    userCustomHeadline: firstString(payload.user_custom_headline, payload.userCustomHeadline, currentBrief.user_custom_headline),
    userCustomSubcopy: firstString(payload.user_custom_subcopy, payload.userCustomSubcopy, currentBrief.user_custom_subcopy),
    sourceImagePath: firstString(payload.source_image_path, payload.sourceImagePath) || null,
    referenceImagePath: firstString(payload.reference_image_path, payload.referenceImagePath) || null,
    selectedReferenceTemplateId: firstString(snapshot.selected_reference_template_id, payload.selected_reference_template_id, payload.selectedReferenceTemplateId) || null,
    selectedReferenceTemplateTitle: firstString(asRecord(snapshot.reference_template_snapshot).title, payload.selected_reference_template_title, payload.selectedReferenceTemplateTitle) || null,
    generationJob: {
      job_id: jobId,
      thread_id: threadId,
      status,
      metadata: currentQuestion ? { pending_interrupt: { type: "option_question", option_question: currentQuestion } } : {}
    },
    currentQuestion,
    conversationMessages
  };
}
```

- [ ] **Step 4: Run mapper tests**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit the mapper**

Run:

```bash
git add apps/web/lib/chat-thread-state-mapper.ts apps/web/lib/chat-thread-state-mapper.test.ts
git commit -m "feat(web): map graph snapshots into chat state"
```

---

## Task 4: Restore Snapshot State In The Chat Reducer

**Files:**
- Modify: `apps/web/types/marketing.ts`
- Modify: `apps/web/lib/chat-flow.ts`
- Modify: `apps/web/lib/chat-flow.test.ts`

- [ ] **Step 1: Write the reducer test**

Append this test to `apps/web/lib/chat-flow.test.ts`:

```ts
it("restores a persisted thread snapshot without losing user context", () => {
  const state = chatFlowReducer(createInitialChatFlowState(), {
    type: "restoreThreadSnapshot",
    prompt: "오늘 저녁 카페 딸기라떼 할인 광고",
    jobId: "job_1",
    threadId: "thread_1",
    context: {
      businessType: "카페",
      itemOrService: "딸기라떼",
      promotionGoal: "할인 이벤트"
    },
    copyGenerationMode: "custom_input",
    selectedChannelId: "instagram-feed",
    selectedTone: "상큼한",
    selectedImageGenerationEngine: "gpt_image_2",
    customDirection: "딸기라떼가 크게 보이게",
    userCustomHeadline: "오늘만 딸기라떼 반값",
    userCustomSubcopy: "오후 2시부터 5시까지",
    sourceImagePath: null,
    referenceImagePath: null,
    selectedReferenceTemplateId: null,
    selectedReferenceTemplateTitle: null,
    generationJob: {
      job_id: "job_1",
      thread_id: "thread_1",
      status: "waiting_user_input"
    },
    currentQuestion: {
      field: "item_or_service",
      question: "홍보할 상품이나 서비스는 무엇인가요?",
      options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
    },
    conversationMessages: [
      { role: "user", text: "오늘 저녁 카페 딸기라떼 할인 광고" },
      { role: "assistant", text: "홍보할 상품이나 서비스는 무엇인가요?" }
    ]
  });

  expect(state.step).toBe(4);
  expect(state.jobId).toBe("job_1");
  expect(state.threadId).toBe("thread_1");
  expect(state.userInput).toBe("오늘 저녁 카페 딸기라떼 할인 광고");
  expect(state.inferredContext.itemOrService).toBe("딸기라떼");
  expect(state.copyGenerationMode).toBe("custom_input");
  expect(state.currentQuestion?.field).toBe("item_or_service");
  expect(state.conversationMessages.at(0)?.text).toBe("오늘 저녁 카페 딸기라떼 할인 광고");
});
```

- [ ] **Step 2: Run the reducer test and verify failure**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-flow.test.ts
```

Expected: fail because `restoreThreadSnapshot` is not part of `ChatFlowAction`.

- [ ] **Step 3: Add the action type**

In `apps/web/types/marketing.ts`, add this union member before `generationJobRequested`:

```ts
  | {
      type: "restoreThreadSnapshot";
      prompt: string;
      jobId: string;
      threadId: string;
      context: InferredContext;
      copyGenerationMode: CopyGenerationMode;
      selectedChannelId: string;
      selectedTone: string;
      selectedImageGenerationEngine: ImageGenerationEngine;
      customDirection: string;
      userCustomHeadline: string;
      userCustomSubcopy: string;
      sourceImagePath: string | null;
      referenceImagePath: string | null;
      selectedReferenceTemplateId: string | null;
      selectedReferenceTemplateTitle: string | null;
      generationJob: GenerationJob;
      currentQuestion: OptionQuestion | null;
      conversationMessages: ChatTranscriptMessage[];
    }
```

- [ ] **Step 4: Implement reducer restore**

In `apps/web/lib/chat-flow.ts`, add this case before `showResultShell`:

```ts
    case "restoreThreadSnapshot":
      return {
        ...state,
        step: 4,
        progress: {
          current: 4,
          total: 4,
          label: action.currentQuestion ? "추가 정보" : "정보 입력"
        },
        userInput: action.prompt,
        jobId: action.jobId,
        threadId: action.threadId,
        inferredContext: action.context,
        contextSource: "backend",
        copyGenerationMode: action.copyGenerationMode,
        selectedChannelId: action.selectedChannelId,
        selectedTone: action.selectedTone,
        selectedImageGenerationEngine: action.selectedImageGenerationEngine,
        customDirection: action.customDirection,
        userCustomHeadline: action.userCustomHeadline,
        userCustomSubcopy: action.userCustomSubcopy,
        sourceImagePath: action.sourceImagePath,
        referenceImagePath: action.referenceImagePath,
        selectedReferenceTemplateId: action.selectedReferenceTemplateId,
        selectedReferenceTemplateTitle: action.selectedReferenceTemplateTitle,
        generationJob: action.generationJob,
        currentQuestion: action.currentQuestion,
        conversationMessages: action.conversationMessages.length > 0
          ? action.conversationMessages
          : action.prompt
            ? [{ role: "user", text: action.prompt }]
            : state.conversationMessages,
        isLoading: false,
        errorMessage: null
      };
```

- [ ] **Step 5: Run reducer tests**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-flow.test.ts
```

Expected: pass.

- [ ] **Step 6: Commit reducer restore**

Run:

```bash
git add apps/web/types/marketing.ts apps/web/lib/chat-flow.ts apps/web/lib/chat-flow.test.ts
git commit -m "fix(web): restore graph chat state without reset"
```

---

## Task 5: Use Snapshot Mapper In ChatGenerateClient

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add a UI restore regression test**

In `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, add `getChatThreadState` to the existing `vi.mock("@/lib/api-client", () => ({ ... }))` object:

```ts
  getChatThreadState: vi.fn(async () => ({
    success: true,
    snapshot: {
      snapshot_id: "snapshot_waiting",
      thread_id: "thread_waiting",
      job_id: "job_waiting",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "waiting_user_input",
      state_payload: {
        user_input: "광고 만들어줘",
        business_type: "카페",
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "item_or_service",
            question: "홍보할 상품이나 서비스는 무엇인가요?",
            options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
          }
        }
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    }
  })),
```

Then update the `next/navigation` mock so `useSearchParams()` can be overridden per test:

```ts
const searchParamsMock = vi.hoisted(() => ({
  value: new URLSearchParams()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    back: navigationMock.back,
    replace: navigationMock.replace
  }),
  useSearchParams: () => searchParamsMock.value
}));
```

Add this test inside `describe("ChatGenerateClient", () => { ... })`:

```ts
it("restores waiting graph question from a thread snapshot", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  searchParamsMock.value = new URLSearchParams("threadId=thread_waiting");
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  render(<ChatGenerateClient initialSurface="chat" />);

  expect(await screen.findByText("홍보할 상품이나 서비스는 무엇인가요?")).toBeInTheDocument();
  expect(screen.getByText("광고 만들어줘")).toBeInTheDocument();
  expect(screen.getByText("카페")).toBeInTheDocument();
});
```

Assert these visible strings:

```ts
expect(await screen.findByText("홍보할 상품이나 서비스는 무엇인가요?")).toBeInTheDocument();
expect(screen.getByText("광고 만들어줘")).toBeInTheDocument();
expect(screen.getByText("카페")).toBeInTheDocument();
```

- [ ] **Step 2: Run the client test and verify failure**

Run:

```bash
cd apps/web && npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: fail because the component dispatches `reset` and does not map `pending_interrupt`.

- [ ] **Step 3: Import the mapper**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, add:

```ts
import { mapChatThreadSnapshotToRestoreState } from "@/lib/chat-thread-state-mapper";
```

- [ ] **Step 4: Replace the `threadIdParam` restore branch**

In the `useEffect` that starts with `if (threadIdParam)`, replace the current `getChatThreadState(...).then(...)` body with:

```ts
      getChatThreadState(threadIdParam).then((res) => {
        const restoreState = mapChatThreadSnapshotToRestoreState(res.snapshot);
        if (!restoreState) {
          showToast("대화 기록을 불러왔지만 이어갈 정보가 비어 있어요.");
          return;
        }

        dispatch({ type: "restoreThreadSnapshot", ...restoreState });
        setShowHistory(false);
        setGenerationProgress(restoreState.currentQuestion ? 65 : 80);
        setGenerationStage(restoreState.currentQuestion ? "jobQuestion" : "brief");
        lastPrimedStageRef.current = restoreState.currentQuestion ? "generating" : "brief";
      }).catch(() => {
        showToast("대화 기록을 불러오는데 실패했습니다.");
      });
```

Do not keep the old `dispatch({ type: "reset" })` inside this branch.

- [ ] **Step 5: Run focused web tests**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts lib/chat-flow.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit client restore**

Run:

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "fix(web): resume graph chat questions from snapshots"
```

---

## Task 6: Stop Rendering Backend-Local Artifact Paths

**Files:**
- Modify: `apps/web/lib/generation-result-utils.ts`
- Modify: `apps/web/lib/generation-result-utils.test.ts`

- [ ] **Step 1: Update local artifact tests**

In `apps/web/lib/generation-result-utils.test.ts`, replace the test named `uses generated asset proxy URLs for local artifact paths` with:

```ts
  it("does not expose local artifact paths as browser image URLs", () => {
    const payload = doneJobLocalPathOnly.result_payload;

    expect(getDisplayImageUrl(payload)).toBeNull();
    expect(getDownloadUrl(payload)).toBeNull();
    expect(resolvePreviewImageUrl(doneJobLocalPathOnly)).toBeNull();
    expect(resolveDownloadUrl(doneJobLocalPathOnly)).toBeNull();
    expect(shouldShowImagePreview(payload)).toBe(false);
    expect(shouldEnableDownload(payload)).toBe(false);
    expect(hasOnlyLocalArtifactPath(payload)).toBe(true);
    expect(isDownloadEnabled(doneJobLocalPathOnly)).toBe(false);
  });
```

In the copy text test for local paths, replace the URL expectations with:

```ts
    expect(text).toContain("Image URL: not available yet");
    expect(text).toContain("Download URL: not available yet");
```

In the status notice test, replace the local-path-only expectation with:

```ts
    expect(getGenerationResultNotice(doneJobLocalPathOnly)).toEqual({
      level: "warning",
      message: "이미지는 생성됐지만 보관함에서 확인할 수 있는 주소가 아직 연결되지 않았어요."
    });
```

- [ ] **Step 2: Run result utils tests and verify failure**

Run:

```bash
cd apps/web && npm test -- --run lib/generation-result-utils.test.ts
```

Expected: fail because local paths are still converted by `firstGeneratedAssetUrl()`.

- [ ] **Step 3: Remove generated-asset fallback from URL resolution**

In `apps/web/lib/generation-result-utils.ts`, remove this import:

```ts
import { buildGeneratedAssetUrl } from "./generated-assets";
```

Replace `getDisplayImageUrl()` with:

```ts
export function getDisplayImageUrl(payload: ResultArtifactPayload | null | undefined): string | null {
  return firstPublicUrl(
    payload?.final_image_url,
    payload?.preview_image_url,
    payload?.copy_visual_preview_url,
    payload?.download_url
  );
}
```

Replace `getDownloadUrl()` with:

```ts
export function getDownloadUrl(payload: ResultArtifactPayload | null | undefined): string | null {
  return firstPublicUrl(
    payload?.download_url,
    payload?.final_image_url,
    payload?.preview_image_url,
    payload?.copy_visual_preview_url
  );
}
```

Delete the `firstGeneratedAssetUrl()` helper from this file.

In `getGenerationResultNotice()`, replace the `hasOnlyLocalArtifactPath(payload)` branch message with:

```ts
      return { level: "warning", message: "이미지는 생성됐지만 보관함에서 확인할 수 있는 주소가 아직 연결되지 않았어요." };
```

- [ ] **Step 4: Run result utils tests**

Run:

```bash
cd apps/web && npm test -- --run lib/generation-result-utils.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit URL policy**

Run:

```bash
git add apps/web/lib/generation-result-utils.ts apps/web/lib/generation-result-utils.test.ts
git commit -m "fix(web): require browser-safe result image urls"
```

---

## Task 7: Replace Complete Screen With Archive-First UX

**Files:**
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Create: `apps/web/components/generate/GenerationCompleteStep.test.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`

- [ ] **Step 1: Add component tests**

Create `apps/web/components/generate/GenerationCompleteStep.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createInitialChatFlowState } from "@/lib/chat-flow";
import { GenerationCompleteStep } from "./GenerationCompleteStep";

function renderStep(overrides = {}) {
  const state = {
    ...createInitialChatFlowState(),
    step: 4,
    generationJob: {
      job_id: "job_local",
      status: "done",
      result_payload: {
        final_image_url: null,
        download_url: null,
        final_image_path: "data/outputs/job_local/final_0.png"
      }
    },
    ...overrides
  };
  const onOpenArchive = vi.fn();
  render(
    <GenerationCompleteStep
      state={state}
      onBrowseSimilar={vi.fn()}
      onGoHome={vi.fn()}
      onRegenerate={vi.fn()}
      onOpenArchive={onOpenArchive}
    />
  );
  return { onOpenArchive };
}

describe("GenerationCompleteStep", () => {
  it("does not render a generated image for local-only artifacts", () => {
    renderStep();

    expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeInTheDocument();
    expect(screen.getByText("완성된 이미지는 보관함에서 확인할 수 있어요.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("opens archive from the primary CTA", () => {
    const { onOpenArchive } = renderStep();

    fireEvent.click(screen.getByRole("button", { name: "보관함에서 확인하기" }));

    expect(onOpenArchive).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run component test and verify failure**

Run:

```bash
cd apps/web && npm test -- --run components/generate/GenerationCompleteStep.test.tsx
```

Expected: fail because `onOpenArchive` is not a prop and the current screen still renders result-card logic.

- [ ] **Step 3: Replace completion props**

In `apps/web/components/generate/GenerationCompleteStep.tsx`, change the prop type to:

```ts
type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
  onGoHome: () => void;
  onRegenerate: () => void;
  onOpenArchive: () => void;
};
```

- [ ] **Step 4: Replace the completion rendering**

Inside `GenerationCompleteStep`, keep `generatedJob`, `resultPayload`, `resultNotice`, `hasLocalOnlyArtifact`, and `selectedEngineLabel`. Replace generated creative/card rendering with this status model:

```ts
  const isFailed = generatedJob?.status === "failed";
  const isDone = generatedJob?.status === "done";
  const isInProgress = Boolean(generatedJob && !isDone && !isFailed);
  const title = isFailed
    ? "이미지 생성에 실패했어요"
    : isDone
      ? "광고 이미지 생성이 완료됐어요"
      : isInProgress
        ? "광고 이미지 생성이 진행 중이에요"
        : "생성 요청 내역이 없어요";
  const description = isFailed
    ? resultNotice.message
    : isDone
      ? "완성된 이미지는 보관함에서 확인할 수 있어요."
      : isInProgress
        ? "완료되면 보관함에 자동으로 정리돼요."
        : "대화로 광고를 만들면 생성 요청 상태가 여기에 표시돼요.";
```

Return this JSX shape:

```tsx
    <>
      <StepHeader title="GENERATED RESULTS" canGoBack onBack={onGoHome} />

      <header className={styles.resultsHeader}>
        <MascotImage role={isFailed ? "errorWorried" : "completeCheck"} decorative className={styles.resultsMascot} />
        <h1>{title}</h1>
        <p>{description}</p>
        <div className={styles.resultChips} aria-label="생성 요청 정보">
          <span>{selectedEngineLabel}</span>
          {generatedJob?.status ? <span>{generatedJob.status}</span> : null}
        </div>
      </header>

      <section className={styles.emptyResultPanel} aria-label="보관함 안내">
        <strong>{isDone ? "보관함에서 결과물을 확인해주세요" : isFailed ? "요청을 다시 시도해주세요" : "생성 요청을 처리하고 있어요"}</strong>
        <p>
          {isDone
            ? "이미지 미리보기는 보관함에 저장된 결과 기준으로만 보여드려요."
            : isFailed
              ? "실패한 요청은 임의 이미지로 대체하지 않아요."
              : "완료 전에는 깨진 이미지나 임시 카드를 보여주지 않아요."}
        </p>
      </section>

      {hasLocalOnlyArtifact ? (
        <p className={styles.savedNotice}>
          <Info size={18} aria-hidden="true" />
          이미지는 생성됐지만 보관함에서 확인할 수 있는 주소가 아직 연결되지 않았어요.
        </p>
      ) : null}

      {generatedJob ? (
        <p className={styles.savedNotice} data-result-notice-level={resultNotice.level}>
          <Info size={18} aria-hidden="true" />
          {resultNotice.message}
        </p>
      ) : null}

      <ValidationSummaryPanel payload={resultPayload} />

      <div className={styles.stepFooter}>
        <div className={`${styles.actionGrid} ${styles.generatedResultActions}`}>
          <button className={styles.primaryButton} type="button" onClick={onOpenArchive}>
            보관함에서 확인하기 <Sparkles size={18} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button" onClick={onRegenerate}>
            <RotateCcw size={17} aria-hidden="true" />
            새 요청으로 만들기
          </button>
          <button className={styles.secondaryButton} type="button" onClick={onGoHome}>
            <Home size={17} aria-hidden="true" />
            홈으로
          </button>
        </div>
        <button className={styles.textButton} type="button" onClick={onBrowseSimilar}>
          참고할 스타일 더 보기
        </button>
      </div>
    </>
```

Remove unused imports from `GenerationCompleteStep.tsx`: `CheckCircle2`, `Download`, `ImageOff`, `Share2`, `buildGeneratedAssetUrl`, `buildGenerationResultCopyText`, `isDownloadEnabled`, `resolveDownloadUrl`, `resolvePreviewImageUrl`, `CreativeTone`, `MockCreative`, `AdCreativeCard`.

- [ ] **Step 5: Update ChatGenerateClient props**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, replace the `GenerationCompleteStep` props with:

```tsx
        <GenerationCompleteStep
          state={state}
          onBrowseSimilar={() => {
            setGenerationStage("similarBrowsing");
            lastPrimedStageRef.current = "similar";
            navigateTo("chat", "similar");
          }}
          onGoHome={() => navigateTo("home")}
          onRegenerate={() => {
            handleOpenFreshChat();
          }}
          onOpenArchive={() => navigateTo("ads")}
        />
```

- [ ] **Step 6: Run component and chat tests**

Run:

```bash
cd apps/web && npm test -- --run components/generate/GenerationCompleteStep.test.tsx app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: pass after updating old text expectations in `ChatGenerateClient.test.tsx` from direct preview wording to archive-first wording.

- [ ] **Step 7: Commit archive-first completion UI**

Run:

```bash
git add apps/web/components/generate/GenerationCompleteStep.tsx apps/web/components/generate/GenerationCompleteStep.test.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "fix(web): move generation completion to archive-first ux"
```

---

## Task 8: Keep Generation Polling But Stop Promising Immediate Preview

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add polling completion assertion**

In `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, add or update the test that completes a generation job with this `result_payload`:

```ts
{
  final_image_url: null,
  download_url: null,
  final_image_path: "data/outputs/job_1/final_0.png"
}
```

Assert:

```ts
expect(await screen.findByText("광고 이미지 생성이 완료됐어요")).toBeInTheDocument();
expect(screen.getByText("완성된 이미지는 보관함에서 확인할 수 있어요.")).toBeInTheDocument();
expect(screen.queryByRole("img")).not.toBeInTheDocument();
```

- [ ] **Step 2: Run chat tests**

Run:

```bash
cd apps/web && npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: pass. If it fails because the test still expects `찰떡 광고 시안이 완성됐어요`, update that expectation to `광고 이미지 생성이 완료됐어요`.

- [ ] **Step 3: Confirm polling still routes waiting questions**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts lib/chat-flow.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: pass, including waiting-user-input tests.

- [ ] **Step 4: Commit polling wording updates**

Run only if this task changed test or client files:

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "test(web): cover archive-first generation completion"
```

---

## Task 9: Full Verification

**Files:**
- Verify only; no file changes expected.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
uv run python -m pytest orchestrator/tests/test_multiturn_state_api.py orchestrator/tests/test_chat_thread_service.py orchestrator/tests/test_generation_job_graph_execution.py -q
```

Expected: pass.

- [ ] **Step 2: Run web focused tests**

Run:

```bash
cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts lib/chat-flow.test.ts lib/generation-result-utils.test.ts components/generate/GenerationCompleteStep.test.tsx app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: pass.

- [ ] **Step 3: Run TypeScript check**

Run:

```bash
cd apps/web && npx tsc --noEmit
```

Expected: pass with no type errors.

- [ ] **Step 4: Run local manual smoke**

Start three terminals:

```bash
set -a; source .env; set +a
EASYADS_DB_BACKEND=postgres uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
set -a; source .env; set +a
cd apps/bff && npm run dev
```

```bash
set -a; source .env; set +a
cd apps/web && npm run dev
```

Then check `http://localhost:3000`:

1. Open `대화로 시작하기`.
2. Enter `카페 딸기라떼 할인 광고 만들어줘`.
3. Confirm the next question keeps `카페` and does not reset the context panel to blank/default values.
4. Answer missing context questions.
5. Confirm the complete screen says the generated image can be checked from the archive.
6. Confirm no broken image placeholder appears.

- [ ] **Step 5: Confirm git state**

Run:

```bash
git status --short --branch
```

Expected: clean branch or only intentionally uncommitted notes.

---

## Task 10: PR Notes

**Files:**
- Verify only; no file changes expected.

- [ ] **Step 1: Prepare PR summary**

Use this PR summary:

```md
## 작업 개요
- LangGraph thread snapshot 복원 시 thread가 실제로 속한 workspace 기준으로 state를 조회하도록 수정했습니다.
- 프론트엔드에서 persisted graph state(snake_case)를 chat reducer state(camelCase)로 매핑하는 복원 로직을 추가했습니다.
- 생성 완료 화면을 직접 이미지 미리보기 중심에서 보관함 확인 중심 UX로 변경했습니다.
- 브라우저에서 접근할 수 없는 `data/outputs/...` 로컬 경로를 이미지 URL로 변환하지 않도록 결과 URL 정책을 수정했습니다.

## 확인 방법
- `uv run python -m pytest orchestrator/tests/test_multiturn_state_api.py orchestrator/tests/test_chat_thread_service.py orchestrator/tests/test_generation_job_graph_execution.py -q`
- `cd apps/web && npm test -- --run lib/chat-thread-state-mapper.test.ts lib/chat-flow.test.ts lib/generation-result-utils.test.ts components/generate/GenerationCompleteStep.test.tsx app/generate/chat/ChatGenerateClient.test.tsx`
- `cd apps/web && npx tsc --noEmit`

## 기대 효과
- 사용자가 입력한 대화 내용과 LangGraph가 물어본 추가 질문이 UI에서 리셋되지 않습니다.
- 실제 브라우저 표시 URL이 없는 생성 결과는 깨진 이미지로 보이지 않습니다.
- 생성 결과 확인 동선이 보관함 중심으로 정리됩니다.
```

- [ ] **Step 2: Confirm commit grouping**

Expected commit groups:

```bash
git log --oneline --decorate -8
```

Expected recent subjects include:

```text
fix(orchestrator): resolve chat thread owning workspace
fix(orchestrator): restore graph snapshots from thread workspace
feat(web): map graph snapshots into chat state
fix(web): restore graph chat state without reset
fix(web): resume graph chat questions from snapshots
fix(web): require browser-safe result image urls
fix(web): move generation completion to archive-first ux
test(web): cover archive-first generation completion
```

## Self-Review Checklist

- [ ] The plan covers both reported issues: context reset and broken immediate image preview.
- [ ] Backend tasks are isolated from frontend UX tasks.
- [ ] Tests are written before implementation in every behavior-changing task.
- [ ] Local-only artifact paths never become display/download URLs.
- [ ] The archive-first screen still keeps retry, home, and archive navigation.
- [ ] The mapper explicitly handles `pending_interrupt.option_question`.
- [ ] Verification includes backend tests, web tests, TypeScript, and manual smoke.
