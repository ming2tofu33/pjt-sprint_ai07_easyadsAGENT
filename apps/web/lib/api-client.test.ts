import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createBrandKit,
  createGenerationJob,
  fetchReferenceDetail,
  fetchReferences,
  fetchSimilarReferences,
  getBrandKit,
  getCurrentBrandKit,
  getGenerationJob,
  startPhotoGeneration,
  updateBrandKit,
  uploadPhotoAsset
} from "./api-client";

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
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
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

describe("api-client backend contract routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("fetches reference catalog endpoints through the BFF", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ success: true, items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchReferences({ category: "cafe", tags: ["CTA", "warm"], limit: 2 });
    await fetchReferenceDetail("template_1");
    await fetchSimilarReferences("template_1", { limit: 3 });

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:4000/api/references?category=cafe&tags=CTA&tags=warm&limit=2");
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/references/template_1");
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://127.0.0.1:4000/api/references/template_1/similar?limit=3");
  });

  it("calls brand kit endpoints through the BFF", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    await getCurrentBrandKit({ userId: "user_1" });
    await createBrandKit({ store_name: "Moon Cafe", business_type: "cafe" });
    await getBrandKit("bk_1");
    await updateBrandKit("bk_1", { store_name: "Sun Cafe" });

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:4000/api/brand-kits/current?user_id=user_1");
    expect(fetchMock.mock.calls[1][0]).toBe("http://127.0.0.1:4000/api/brand-kits");
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://127.0.0.1:4000/api/brand-kits/bk_1");
    expect(fetchMock.mock.calls[3][0]).toBe("http://127.0.0.1:4000/api/brand-kits/bk_1");
    expect(fetchMock.mock.calls[3][1]).toEqual(expect.objectContaining({ method: "PATCH" }));
  });

  it("calls generation job endpoints through the BFF", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    await createGenerationJob({ user_input: "Create an ad" });
    await getGenerationJob("job_1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:4000/api/generation-jobs");
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/generation-jobs/job_1");
  });
});
