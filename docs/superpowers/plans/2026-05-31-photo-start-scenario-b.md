# Photo Start Scenario B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect Scenario B, "내 사진으로 만들기", to the existing backend generation flow by using `photo_start` as the entry point and then reusing the current chat state, question loop, copy selection, brief, and generated result screens.

**Architecture:** The photo flow gets only one new backend entry lane: upload a user image, pass its saved `sourceImagePath` into `photo_start`, and normalize the response into the same `ChatTurnResponse` shape already used by chat start. The frontend stops running a separate mock photo wizard after upload; once `photo_start` returns, it dispatches the same reducer actions used by chat and navigates into the existing chat screens. The existing T2I lane remains unchanged, so local `.env` continues to use the `gpt_image_2` engine lane with `T2I_GPT_IMAGE_MODEL=gpt-image-1`.

**Tech Stack:** FastAPI, LangGraph, Pydantic, Fastify, Zod, Node `fs/promises`, Next.js 14, React, TypeScript, Vitest, Testing Library, Pytest.

---

## File Structure

- Create `orchestrator/app/api/photo.py`
  - Defines `/v1/marketing/photo/start`.
  - Builds graph input with `entry_mode: "photo_start"` and `source_image_path`.
  - Returns `ChatStartResponse | ChatOptionQuestionResponse`, matching chat start.
- Modify `orchestrator/app/main.py`
  - Includes the new photo router.
- Modify `orchestrator/tests/test_chat_api.py`
  - Adds API tests for photo start request shape and option-question propagation.
- Modify `apps/bff/src/app.js`
  - Adds JSON image upload endpoint and photo start proxy endpoint.
  - Stores uploaded files under an injected test upload dir or `data/uploads`.
- Modify `apps/bff/tests/generate.test.js`
  - Adds tests for upload validation, upload save path, and photo start proxy.
- Modify `apps/web/lib/api-client.ts`
  - Adds `uploadPhotoAsset()` and `startPhotoGeneration()`.
- Create `apps/web/lib/api-client.test.ts`
  - Verifies API client request payloads and error propagation.
- Modify `apps/web/components/generate/PhotoGenerateStep.tsx`
  - Replaces the internal mock 4-step wizard with upload + prompt start.
  - Shows only upload state, selected file, prompt, and backend error/loading state.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Adds a photo-start handler that uploads the file, calls photo start, then dispatches existing chat reducer actions.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Replaces the photo sample-flow test with a real photo-start handoff test.

---

### Task 1: Orchestrator Photo Start API

**Files:**
- Create: `orchestrator/app/api/photo.py`
- Modify: `orchestrator/app/main.py`
- Test: `orchestrator/tests/test_chat_api.py`

- [ ] **Step 1: Write the failing orchestrator tests**

Append these tests to `orchestrator/tests/test_chat_api.py`:

```python
def test_photo_start_invokes_graph_with_photo_entry(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
            captured["config"] = config
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "copy_candidates": [{"id": "copy_1", "headline": "사진 속 메뉴를 오늘의 신메뉴로"}],
            }

    from orchestrator.app.api import photo as photo_api

    monkeypatch.setattr(photo_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "이 사진으로 신메뉴 광고 만들어줘",
            "sourceImagePath": "data/uploads/menu.png",
            "adFormat": "instagram_feed",
            "renderProfile": "premium_api",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"].startswith("photo_")
    assert payload["threadId"].endswith("_thread")
    assert payload["context"]["itemOrService"] == "딸기라떼"
    assert payload["copyCandidates"][0]["headline"] == "사진 속 메뉴를 오늘의 신메뉴로"
    assert captured["state"]["entry_mode"] == "photo_start"
    assert captured["state"]["source_image_path"] == "data/uploads/menu.png"
    assert captured["state"]["render_profile"] == "premium_api"
    assert captured["state"]["copy_generation_mode"] == "suggest_candidates"
    assert captured["state"]["context"]["extra"]["ad_format"] == "instagram_feed"
    assert captured["config"]["configurable"]["thread_id"] == payload["threadId"]


def test_photo_start_can_return_option_question(monkeypatch):
    class FakeGraph:
        def invoke(self, state, config):
            return {
                "__interrupt__": [
                    type(
                        "InterruptValue",
                        (),
                        {
                            "value": {
                                "type": "option_question",
                                "job_id": state["job_id"],
                                "thread_id": state["thread_id"],
                                "option_question": {
                                    "field": "business_type",
                                    "question": "어떤 업종의 광고인가요?",
                                    "options": [{"id": 1, "label": "카페/디저트", "value": "cafe"}],
                                },
                            }
                        },
                    )()
                ],
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "waiting_user_selection",
                "context": {"extra": {}},
                "missing_fields": ["business_type"],
            }

    from orchestrator.app.api import photo as photo_api

    monkeypatch.setattr(photo_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={"userInput": "이 사진으로 광고 만들어줘", "sourceImagePath": "data/uploads/menu.png"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "option_question"
    assert payload["question"]["field"] == "business_type"
    assert payload["missingFields"] == ["business_type"]
```

- [ ] **Step 2: Run the failing orchestrator test**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_api.py::test_photo_start_invokes_graph_with_photo_entry -q
```

Expected: FAIL with `404 Not Found` for `/v1/marketing/photo/start`.

- [ ] **Step 3: Add the photo router**

Create `orchestrator/app/api/photo.py` with this content:

```python
"""Photo-start API adapter for the marketing graph."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import Field

from orchestrator.app.api.chat import (
    CamelModel,
    ChatOptionQuestionResponse,
    ChatStartResponse,
    _copy_candidates_response,
    _interrupt_value,
    _option_question_response,
    _thread_config,
)
from orchestrator.app.graph.builder import build_marketing_graph

router = APIRouter(prefix="/v1/marketing/photo", tags=["marketing-photo"])
_GRAPH = build_marketing_graph()


class PhotoStartRequest(CamelModel):
    user_input: str = Field(alias="userInput", min_length=1)
    source_image_path: str = Field(alias="sourceImagePath", min_length=1)
    ad_format: str = Field(default="instagram_feed", alias="adFormat")
    render_profile: str = Field(default="premium_api", alias="renderProfile")
    vision_preprocess_mode: str = Field(default="resize_only", alias="visionPreprocessMode")


@router.post("/start", response_model=ChatStartResponse | ChatOptionQuestionResponse, response_model_by_alias=True)
def start_photo(request: PhotoStartRequest) -> ChatStartResponse | ChatOptionQuestionResponse:
    job_seed = f"{request.source_image_path}:{request.user_input}"
    job_id = f"photo_{abs(hash(job_seed))}"
    thread_id = f"{job_id}_thread"
    state = {
        "entry_mode": "photo_start",
        "user_input": request.user_input,
        "source_image_path": request.source_image_path,
        "job_id": job_id,
        "thread_id": thread_id,
        "render_profile": request.render_profile,
        "vision_preprocess_mode": request.vision_preprocess_mode,
        "copy_generation_mode": "suggest_candidates",
        "context": {
            "extra": {
                "ad_format": request.ad_format,
                "source_image_path": request.source_image_path,
            }
        },
    }
    result = _GRAPH.invoke(state, config=_thread_config(thread_id))
    interrupt = _interrupt_value(result)

    if interrupt and interrupt.get("type") == "option_question":
        return _option_question_response(result, interrupt)

    return _copy_candidates_response(result, job_id=job_id, thread_id=thread_id, interrupt=interrupt)
```

- [ ] **Step 4: Include the photo router in FastAPI**

Modify `orchestrator/app/main.py`:

```python
from orchestrator.app.api.chat import router as chat_router
from orchestrator.app.api.photo import router as photo_router

app = FastAPI(title="EasyAds Orchestrator", version="0.1.0")
app.include_router(chat_router)
app.include_router(photo_router)
```

- [ ] **Step 5: Run the orchestrator photo tests**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_api.py::test_photo_start_invokes_graph_with_photo_entry orchestrator/tests/test_chat_api.py::test_photo_start_can_return_option_question -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add orchestrator/app/api/photo.py orchestrator/app/main.py orchestrator/tests/test_chat_api.py
git commit -m "feat(orchestrator): add photo start endpoint"
```

---

### Task 2: BFF Upload and Photo Proxy

**Files:**
- Modify: `apps/bff/src/app.js`
- Test: `apps/bff/tests/generate.test.js`

- [ ] **Step 1: Write the failing BFF tests**

Append these tests to `apps/bff/tests/generate.test.js`:

```js
it("saves JSON photo uploads and returns a source image path", async () => {
  const uploadDir = await fs.mkdtemp(path.join(os.tmpdir(), "easyads-upload-"));
  const app = buildApp({ fetchImpl: vi.fn(), uploadDir });
  const dataUrl = `data:image/png;base64,${Buffer.from("fake image bytes").toString("base64")}`;

  const response = await app.inject({
    method: "POST",
    url: "/api/generate/photo/upload",
    payload: {
      filename: "menu photo.png",
      mimeType: "image/png",
      dataUrl
    }
  });

  expect(response.statusCode).toBe(200);
  const payload = response.json();
  expect(payload.sourceImagePath).toMatch(/^data\/uploads\/photo_/);
  expect(payload.sourceImagePath.endsWith(".png")).toBe(true);
  expect(payload.fileName).toBe("menu photo.png");
  expect(payload.mimeType).toBe("image/png");
  await expect(fs.readFile(path.join(uploadDir, path.basename(payload.sourceImagePath)))).resolves.toEqual(Buffer.from("fake image bytes"));
  await app.close();
});

it("validates JSON photo upload payloads", async () => {
  const app = buildApp({ fetchImpl: vi.fn() });

  const response = await app.inject({
    method: "POST",
    url: "/api/generate/photo/upload",
    payload: {
      filename: "menu.txt",
      mimeType: "text/plain",
      dataUrl: "data:text/plain;base64,ZmFrZQ=="
    }
  });

  expect(response.statusCode).toBe(400);
  expect(response.json().error).toBe("invalid_request");
  await app.close();
});

it("proxies photo start requests to the orchestrator", async () => {
  const fetchImpl = vi.fn(async () =>
    jsonResponse({
      jobId: "photo_1",
      threadId: "photo_1_thread",
      status: "generating_copy_candidates",
      context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
      copyCandidates: [{ id: "copy_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
      recommendedCopyId: "copy_1"
    })
  );
  const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

  const response = await app.inject({
    method: "POST",
    url: "/api/generate/photo/start",
    payload: {
      userInput: "이 사진으로 신메뉴 광고 만들어줘",
      sourceImagePath: "data/uploads/photo_abc.png",
      adFormat: "instagram_feed",
      renderProfile: "premium_api"
    }
  });

  expect(response.statusCode).toBe(200);
  expect(response.json().jobId).toBe("photo_1");
  expect(fetchImpl).toHaveBeenCalledWith(
    "http://orchestrator/v1/marketing/photo/start",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        userInput: "이 사진으로 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_abc.png",
        adFormat: "instagram_feed",
        renderProfile: "premium_api"
      })
    })
  );
  await app.close();
});
```

Add these imports at the top of `apps/bff/tests/generate.test.js`:

```js
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
```

- [ ] **Step 2: Run the failing BFF test**

Run:

```bash
cd apps/bff && npm test -- tests/generate.test.js
```

Expected: FAIL because `/api/generate/photo/upload` and `/api/generate/photo/start` do not exist.

- [ ] **Step 3: Implement upload and photo start in BFF**

Modify `apps/bff/src/app.js` with these imports:

```js
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
```

Add these schemas below `chatAnswerSchema`:

```js
const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"];

const photoUploadSchema = z.object({
  filename: z.string().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().min(1)
});

const photoStartSchema = z.object({
  userInput: z.string().min(1),
  sourceImagePath: z.string().min(1),
  adFormat: z.string().optional(),
  renderProfile: z.string().optional()
});
```

Add these helpers above `buildApp()`:

```js
function extensionForMimeType(mimeType) {
  if (mimeType === "image/jpeg") {
    return ".jpg";
  }
  if (mimeType === "image/webp") {
    return ".webp";
  }
  return ".png";
}

function decodeDataUrl(dataUrl, mimeType) {
  const prefix = `data:${mimeType};base64,`;
  if (!dataUrl.startsWith(prefix)) {
    const error = new Error("dataUrl mime type does not match mimeType");
    error.statusCode = 400;
    throw error;
  }
  return Buffer.from(dataUrl.slice(prefix.length), "base64");
}

function publicUploadPath(fileName) {
  return `data/uploads/${fileName}`;
}
```

Inside `buildApp()`, add this after `fetchImpl`:

```js
  const uploadDir = options.uploadDir ?? process.env.BFF_UPLOAD_DIR ?? path.resolve(process.cwd(), "../../data/uploads");
```

Add these routes after `/api/generate/chat/answer`:

```js
  app.post("/api/generate/photo/upload", async (request, reply) => {
    const parsed = photoUploadSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    const imageBuffer = decodeDataUrl(parsed.data.dataUrl, parsed.data.mimeType);
    const extension = extensionForMimeType(parsed.data.mimeType);
    const savedName = `photo_${crypto.randomUUID()}${extension}`;
    await fs.mkdir(uploadDir, { recursive: true });
    await fs.writeFile(path.join(uploadDir, savedName), imageBuffer);

    return {
      sourceImagePath: publicUploadPath(savedName),
      fileName: parsed.data.filename,
      mimeType: parsed.data.mimeType,
      sizeBytes: imageBuffer.length
    };
  });

  app.post("/api/generate/photo/start", async (request, reply) => {
    const parsed = photoStartSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: "invalid_request", issues: parsed.error.issues });
    }

    return proxyJson({
      fetchImpl,
      url: `${orchestratorBaseUrl}/v1/marketing/photo/start`,
      body: parsed.data
    });
  });
```

- [ ] **Step 4: Run BFF tests**

Run:

```bash
cd apps/bff && npm test -- tests/generate.test.js
```

Expected: all tests in `tests/generate.test.js` pass.

- [ ] **Step 5: Commit**

```bash
git add apps/bff/src/app.js apps/bff/tests/generate.test.js
git commit -m "feat(bff): add photo upload and start routes"
```

---

### Task 3: Web API Client for Photo Start

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Create: `apps/web/lib/api-client.test.ts`

- [ ] **Step 1: Write the failing web API client tests**

Create `apps/web/lib/api-client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { startPhotoGeneration, uploadPhotoAsset } from "./api-client";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("api-client photo generation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uploads a photo file as a JSON data URL", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        sourceImagePath: "data/uploads/photo_1.png",
        fileName: "menu.png",
        mimeType: "image/png",
        sizeBytes: 3
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });

    const result = await uploadPhotoAsset(file);

    expect(result.sourceImagePath).toBe("data/uploads/photo_1.png");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:4000/api/generate/photo/upload",
      expect.objectContaining({
        method: "POST",
        headers: { "content-type": "application/json" }
      })
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0][1].body));
    expect(body.filename).toBe("menu.png");
    expect(body.mimeType).toBe("image/png");
    expect(body.dataUrl).toMatch(/^data:image\/png;base64,/);
  });

  it("starts photo generation with the uploaded source image path", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        jobId: "photo_1",
        threadId: "photo_1_thread",
        status: "generating_copy_candidates",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
        copyCandidates: [{ id: "copy_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
        recommendedCopyId: "copy_1"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await startPhotoGeneration({
      userInput: "이 사진으로 신메뉴 광고 만들어줘",
      sourceImagePath: "data/uploads/photo_1.png"
    });

    expect(result.jobId).toBe("photo_1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:4000/api/generate/photo/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          userInput: "이 사진으로 신메뉴 광고 만들어줘",
          sourceImagePath: "data/uploads/photo_1.png",
          adFormat: "instagram_feed",
          renderProfile: "premium_api"
        })
      })
    );
  });
});
```

- [ ] **Step 2: Run the failing web API tests**

Run:

```bash
cd apps/web && npm test -- lib/api-client.test.ts
```

Expected: FAIL because `uploadPhotoAsset` and `startPhotoGeneration` are not exported.

- [ ] **Step 3: Implement the web API client functions**

Add these types and helpers to `apps/web/lib/api-client.ts`:

```ts
export type PhotoUploadResponse = {
  sourceImagePath: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
};

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result)));
    reader.addEventListener("error", () => reject(new Error("사진 파일을 읽지 못했습니다.")));
    reader.readAsDataURL(file);
  });
}

export async function uploadPhotoAsset(file: File): Promise<PhotoUploadResponse> {
  const dataUrl = await readFileAsDataUrl(file);
  return postJson<PhotoUploadResponse>("/api/generate/photo/upload", {
    filename: file.name,
    mimeType: file.type || "image/png",
    dataUrl
  });
}

export function startPhotoGeneration(input: {
  userInput: string;
  sourceImagePath: string;
  adFormat?: string;
  renderProfile?: string;
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api"
  });
}
```

- [ ] **Step 4: Run the web API tests**

Run:

```bash
cd apps/web && npm test -- lib/api-client.test.ts
```

Expected: all tests in `lib/api-client.test.ts` pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client.test.ts
git commit -m "feat(web): add photo generation api client"
```

---

### Task 4: Frontend Photo Flow Handoff to Chat State

**Files:**
- Modify: `apps/web/components/generate/PhotoGenerateStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write the failing frontend integration test**

In `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, update the API mock to include the two new functions:

```ts
  uploadPhotoAsset: vi.fn(async () => ({
    sourceImagePath: "data/uploads/photo_1.png",
    fileName: "menu.png",
    mimeType: "image/png",
    sizeBytes: 3
  })),
  startPhotoGeneration: vi.fn(async () => ({
    type: "copy_candidates",
    jobId: "photo_1",
    threadId: "photo_1_thread",
    status: "generating_copy_candidates",
    context: {
      businessType: "카페",
      itemOrService: "딸기라떼",
      promotionGoal: "신메뉴 출시"
    },
    copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
    recommendedCopyId: "copy_photo_1"
  })),
```

Replace the current photo sample-flow test with:

```ts
  it("starts real photo generation and joins the existing chat flow", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고에 사용할 사진"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: "사진 기반 생성 시작" }));

    await waitFor(() => expect(api.uploadPhotoAsset).toHaveBeenCalledWith(file));
    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.getByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeTruthy();
    expect(screen.queryByText("AI 분석 결과")).toBeNull();
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
  });
```

- [ ] **Step 2: Run the failing frontend test**

Run:

```bash
cd apps/web && npm test -- app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: FAIL because `PhotoGenerateStep` has no file input and `ChatGenerateClient` has no photo-start handler.

- [ ] **Step 3: Refactor response dispatch into a shared handler**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, replace duplicated `ChatTurnResponse` handling with this helper inside `ChatGenerateClient`:

```tsx
  function applyTurnResponse(prompt: string, response: ChatTurnResponse) {
    if (isQuestionResponse(response)) {
      dispatch({
        type: "backendQuestionReceived",
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        question: response.question
      });
      return;
    }

    dispatch({
      type: "backendStartSucceeded",
      prompt,
      jobId: response.jobId,
      threadId: response.threadId,
      context: response.context,
      copyCandidates: response.copyCandidates,
      recommendedCopyId: response.recommendedCopyId
    });
  }
```

Then update `handleSubmitPrompt()`:

```tsx
  async function handleSubmitPrompt(prompt: string) {
    dispatch({ type: "submitPrompt", prompt });
    try {
      const response = await startChatGeneration(prompt);
      applyTurnResponse(prompt, response);
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "백엔드 연결에 실패했습니다. 잠시 후 다시 시도해주세요."
      });
    }
  }
```

And update `handleAnswerQuestion()` response handling:

```tsx
      const response = await answerChatQuestion({
        jobId: state.jobId,
        threadId: state.threadId,
        field: state.currentQuestion.field,
        value: input.value,
        customText: input.customText
      });
      applyTurnResponse(state.userInput, response);
```

- [ ] **Step 4: Add the photo-start handler**

Update the import in `apps/web/app/generate/chat/ChatGenerateClient.tsx`:

```tsx
import {
  answerChatQuestion,
  createChatBrief,
  startChatGeneration,
  startPhotoGeneration,
  uploadPhotoAsset,
  type ChatTurnResponse
} from "@/lib/api-client";
```

Add this handler inside `ChatGenerateClient`:

```tsx
  async function handleStartPhotoGeneration(input: { file: File; prompt: string }) {
    clearChatFlowSnapshot();
    dispatch({ type: "reset" });
    dispatch({ type: "submitPrompt", prompt: input.prompt });
    try {
      const upload = await uploadPhotoAsset(input.file);
      const response = await startPhotoGeneration({
        userInput: input.prompt,
        sourceImagePath: upload.sourceImagePath
      });
      applyTurnResponse(input.prompt, response);
      lastPrimedStageRef.current = "start";
      navigateTo("chat", "start");
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "사진 기반 생성을 시작하지 못했습니다. 다시 시도해주세요."
      });
      lastPrimedStageRef.current = "start";
      navigateTo("chat", "start");
    }
  }
```

Pass it into `PhotoGenerateStep`:

```tsx
        <PhotoGenerateStep
          onBack={() => router.back()}
          onGoHome={() => navigateTo("home")}
          onOpenChat={handleOpenFreshChat}
          onGenerate={handleStartPhotoGeneration}
        />
```

- [ ] **Step 5: Replace the PhotoGenerateStep mock wizard with upload start**

Replace `apps/web/components/generate/PhotoGenerateStep.tsx` with this component shape:

```tsx
"use client";

import { ArrowRight, FileImage, ImagePlus, MessageCircle, Sparkles, Upload } from "lucide-react";
import { useState } from "react";
import { ChoiceChip } from "./ChoiceChip";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type PhotoGenerateStepProps = {
  onBack: () => void;
  onGoHome: () => void;
  onOpenChat: () => void;
  onGenerate: (input: { file: File; prompt: string }) => Promise<void>;
};

const photoKinds = [
  { label: "음식 사진", prompt: "이 사진으로 신메뉴 광고 만들어줘" },
  { label: "제품 사진", prompt: "이 제품 사진으로 상세 홍보 광고 만들어줘" },
  { label: "매장 사진", prompt: "이 매장 사진으로 방문 유도 광고 만들어줘" },
  { label: "시술 사진", prompt: "이 시술 사진으로 예약 유도 광고 만들어줘" }
];

const photoExamples = [
  "이 사진으로 신메뉴 광고 만들어줘",
  "이 사진으로 예약 홍보 광고 만들어줘",
  "이 사진으로 오픈 이벤트를 알려줘"
];

export function PhotoGenerateStep({ onBack, onGoHome, onOpenChat, onGenerate }: PhotoGenerateStepProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [photoPrompt, setPhotoPrompt] = useState(photoExamples[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const canSubmit = Boolean(selectedFile) && photoPrompt.trim().length > 0 && !isSubmitting;

  async function submitPhotoStart() {
    if (!selectedFile || !photoPrompt.trim()) {
      setErrorMessage("사진과 요청 문구를 함께 입력해주세요.");
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await onGenerate({ file: selectedFile, prompt: photoPrompt.trim() });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "사진 기반 생성을 시작하지 못했습니다.");
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <StepHeader title="사진으로 찰떡 만들기" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onGoHome} />

      <section className={styles.hero}>
        <span className={styles.heroIcon}>
          <ImagePlus size={25} strokeWidth={2.4} aria-hidden="true" />
        </span>
        <h2 className={styles.heroTitle}>사진 한 장으로 광고를 시작해보세요.</h2>
        <p className={styles.heroCopy}>사진을 업로드하면 백엔드가 이미지 전처리와 광고 문구 생성을 이어서 진행해요.</p>
      </section>

      <label className={styles.photoDropzone}>
        <Upload size={23} aria-hidden="true" />
        <h2>{selectedFile ? selectedFile.name : "광고에 사용할 사진 선택"}</h2>
        <p>{selectedFile ? `${Math.ceil(selectedFile.size / 1024)}KB · ${selectedFile.type || "image"}` : "PNG, JPG, WEBP 이미지를 사용할 수 있어요."}</p>
        <input
          aria-label="광고에 사용할 사진"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={(event) => setSelectedFile(event.currentTarget.files?.[0] ?? null)}
        />
      </label>

      <h2 className={styles.sectionTitle}>빠른 시작</h2>
      <div className={styles.chipGrid}>
        {photoKinds.map((item) => (
          <ChoiceChip key={item.label} onClick={() => setPhotoPrompt(item.prompt)}>
            <FileImage size={16} aria-hidden="true" />
            <span>{item.label}</span>
          </ChoiceChip>
        ))}
      </div>

      <h2 className={styles.sectionTitle}>요청 문구</h2>
      <div className={styles.exampleList}>
        {photoExamples.map((example) => (
          <button className={styles.examplePill} key={example} type="button" onClick={() => setPhotoPrompt(example)}>
            <Sparkles size={15} aria-hidden="true" />
            <span>{example}</span>
          </button>
        ))}
      </div>

      <label className={`${styles.inputCard} ${styles.photoInputCard}`}>
        <ImagePlus size={19} aria-hidden="true" />
        <span className={styles.photoInputText}>
          <strong>사진 광고 요청</strong>
          <input
            aria-label="사진 광고 요청 입력"
            value={photoPrompt}
            onChange={(event) => setPhotoPrompt(event.target.value)}
          />
        </span>
      </label>

      {errorMessage ? <p className={styles.errorText}>{errorMessage}</p> : null}

      <div className={styles.stepFooter}>
        <button className={styles.primaryButton} type="button" disabled={!canSubmit} onClick={submitPhotoStart}>
          {isSubmitting ? "사진 분석 요청 중..." : "사진 기반 생성 시작"}
          <ArrowRight size={18} aria-hidden="true" />
        </button>
        <button className={styles.secondaryButton} type="button" onClick={onOpenChat}>
          대화로 시작하기 <MessageCircle size={17} aria-hidden="true" />
        </button>
      </div>
    </>
  );
}
```

- [ ] **Step 6: Add input styling for the request input**

In `apps/web/components/generate/generate.module.css`, add:

```css
.photoDropzone input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.photoInputText input {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--color-text-primary);
  outline: 0;
  font-size: 12px;
  line-height: 1.4;
  font-weight: 800;
}
```

- [ ] **Step 7: Run the frontend photo handoff test**

Run:

```bash
cd apps/web && npm test -- app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: all tests in `ChatGenerateClient.test.tsx` pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/components/generate/PhotoGenerateStep.tsx apps/web/components/generate/generate.module.css apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(web): connect photo start to chat flow"
```

---

### Task 5: End-to-End Verification and Server Restart

**Files:**
- No source files should change in this task.

- [ ] **Step 1: Run targeted test suites**

Run:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests/test_chat_api.py -q
cd apps/bff && npm test -- tests/generate.test.js
cd ../web && npm test -- lib/api-client.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected:

```text
orchestrator/tests/test_chat_api.py passes
apps/bff/tests/generate.test.js passes
apps/web/lib/api-client.test.ts passes
apps/web/app/generate/chat/ChatGenerateClient.test.tsx passes
```

- [ ] **Step 2: Run full regression suites**

Run from repo root:

```bash
PYTHONPATH=. uv run pytest orchestrator/tests -q
cd apps/bff && npm test
cd ../web && npm test
cd ../web && npm run lint
```

Expected:

```text
orchestrator pytest passes
BFF Vitest passes
Web Vitest passes
Next lint reports no warnings or errors
```

- [ ] **Step 3: Build Next.js without a dev-server artifact conflict**

Stop the current web dev server first, then run:

```bash
cd apps/web && npm run build
rm -rf .next
npm run dev -- --hostname 0.0.0.0 --port 3000
```

Expected:

```text
next build completes successfully
dev server is ready at http://localhost:3000
```

- [ ] **Step 4: Restart orchestrator if it was running during the changes**

Run:

```bash
pkill -f "uvicorn orchestrator.app.main:app" || true
uv run uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8010
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8010
```

- [ ] **Step 5: Manual browser check**

Open `http://localhost:3000/generate/photo` and verify:

```text
The page shows a file picker and prompt input.
Selecting a PNG/JPG/WEBP file enables "사진 기반 생성 시작".
Clicking "사진 기반 생성 시작" uploads the image and navigates to /generate/chat.
The next screen is the existing chat flow: either an option question or "AI가 이렇게 이해했어요".
No fixed "딸기라떼 / 핑크톤 / 감성적인 카페 무드" analysis appears unless it came from the backend response.
Continuing through copy selection and brief creation reaches the existing generated result screen.
```

- [ ] **Step 6: Confirm verification did not change source files**

Run:

```bash
git status --short
```

Expected: no new source changes from this verification task. If files changed, inspect the diff before deciding whether a separate commit is needed.

---

## Self-Review

- Spec coverage: The plan covers photo upload, BFF proxying, orchestrator `photo_start`, frontend API client functions, UI mock removal, chat-flow handoff, regression tests, build, and manual browser verification.
- Placeholder scan: The plan contains concrete file paths, test code, route names, request bodies, response shapes, commands, and expected results.
- Type consistency: The same `sourceImagePath`, `userInput`, `adFormat`, `renderProfile`, `ChatTurnResponse`, `copyCandidates`, `recommendedCopyId`, `jobId`, and `threadId` names are used across orchestrator, BFF, web API client, and frontend tests.
