import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApp } from "../src/app.js";

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("generate chat routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("proxies chat start requests to the orchestrator", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        jobId: "job_1",
        threadId: "thread_1",
        status: "generating_copy_candidates",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔" }],
        recommendedCopyId: "copy_1"
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().jobId).toBe("job_1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" })
      })
    );
    await app.close();
  });

  it("validates chat start payloads", async () => {
    const app = buildApp({ fetchImpl: vi.fn() });

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "" }
    });

    expect(response.statusCode).toBe(400);
    expect(response.json().error).toBe("invalid_request");
    await app.close();
  });

  it("proxies brief requests to the orchestrator", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        jobId: "job_1",
        threadId: "thread_1",
        status: "done",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔",
          tone: "상큼한 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경"
        }
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/chat/brief",
      payload: {
        jobId: "job_1",
        threadId: "thread_1",
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "깔끔한",
        customDirection: "제품을 크게"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().brief.copy).toBe("봄을 닮은 한 잔");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/brief",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          jobId: "job_1",
          threadId: "thread_1",
          selectedCopyId: "copy_1",
          selectedChannelId: "instagram-feed",
          selectedTone: "깔끔한",
          customDirection: "제품을 크게"
        })
      })
    );
    await app.close();
  });

  it("proxies context answer requests to the orchestrator", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        type: "option_question",
        jobId: "job_1",
        threadId: "thread_1",
        status: "waiting_user_selection",
        context: { businessType: "카페", itemOrService: null, promotionGoal: null },
        question: {
          field: "item_or_service",
          question: "홍보할 상품이나 서비스는 무엇인가요?",
          options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
        },
        missingFields: ["item_or_service"]
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/chat/answer",
      payload: {
        jobId: "job_1",
        threadId: "thread_1",
        field: "business_type",
        value: "cafe"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().type).toBe("option_question");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/answer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          jobId: "job_1",
          threadId: "thread_1",
          field: "business_type",
          value: "cafe"
        })
      })
    );
    await app.close();
  });

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
    expect(payload.sizeBytes).toBe(Buffer.from("fake image bytes").length);
    await expect(fs.readFile(path.join(uploadDir, path.basename(payload.sourceImagePath)))).resolves.toEqual(
      Buffer.from("fake image bytes")
    );
    await app.close();
    await fs.rm(uploadDir, { recursive: true, force: true });
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
        renderProfile: "premium_api",
        selectedReferenceTemplateId: "template_1"
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
          renderProfile: "premium_api",
          selectedReferenceTemplateId: "template_1"
        })
      })
    );
    await app.close();
  });

  it("proxies generation job selected reference as snake case", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ success: true, job: { job_id: "job_1" } }));
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs",
      payload: { userInput: "Create an ad", selectedReferenceTemplateId: "template_1" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "Create an ad", selected_reference_template_id: "template_1" })
      })
    );
    await app.close();
  });
});
