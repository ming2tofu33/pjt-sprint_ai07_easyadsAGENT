import { afterEach, describe, expect, it, vi } from "vitest";
import { startChatGeneration, startPhotoGeneration, uploadPhotoAsset } from "./api-client";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("api-client photo generation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uploads a photo file as a JSON data URL", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
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
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.filename).toBe("menu.png");
    expect(body.mimeType).toBe("image/png");
    expect(body.dataUrl).toMatch(/^data:image\/png;base64,/);
  });

  it("starts photo generation with the uploaded source image path", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
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

  it("sends no-copy mode for chat and photo generation starts", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        type: "brief_ready",
        jobId: "job_no_copy",
        threadId: "thread_no_copy",
        status: "done",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "광고 홍보" },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await startChatGeneration("딸기라떼 이미지만 만들어줘", { copyGenerationMode: "no_copy" });
    await startPhotoGeneration({
      userInput: "이 사진으로 이미지만 만들어줘",
      sourceImagePath: "data/uploads/photo_1.png",
      copyGenerationMode: "no_copy"
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      userInput: "딸기라떼 이미지만 만들어줘",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "no_copy"
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      userInput: "이 사진으로 이미지만 만들어줘",
      sourceImagePath: "data/uploads/photo_1.png",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "no_copy"
    });
  });

  it("maps image generation configuration errors to actionable messages", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ message: "API call disabled; pass allow_api_call=True or --include-api" }, { status: 502 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      startPhotoGeneration({
        userInput: "이 사진으로 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png"
      })
    ).rejects.toThrow("T2I_ALLOW_API_CALLS=true");
  });
});
