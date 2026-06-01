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
  startChatGeneration,
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

  it("starts chat generation with selected reference template context", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        jobId: "job_1",
        threadId: "thread_1",
        status: "generating_copy_candidates",
        context: { businessType: "cafe", itemOrService: "latte", promotionGoal: "launch" },
        copyCandidates: [{ id: "copy_1", headline: "Latte" }]
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await startChatGeneration("Create an ad", { selectedReferenceTemplateId: "template_1", copyGenerationMode: "auto_pilot" });

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.selectedReferenceTemplateId).toBe("template_1");
    expect(body.copyGenerationMode).toBe("auto_pilot");
  });
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
          renderProfile: "premium_api",
          selectedReferenceTemplateId: undefined,
          copyGenerationMode: undefined
        })
      })
    );
  });

  it("starts photo generation with selected reference template context", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ jobId: "photo_1", threadId: "thread_1", status: "ok", context: {}, copyCandidates: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await startPhotoGeneration({
      userInput: "Create from photo",
      sourceImagePath: "data/uploads/photo_1.png",
      selectedReferenceTemplateId: "template_1",
      copyGenerationMode: "auto_pilot"
    });

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.selectedReferenceTemplateId).toBe("template_1");
    expect(body.copyGenerationMode).toBe("auto_pilot");
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
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed" },
          result_payload: {
            schema_version: "result_artifact_v1",
            final_image_path: "data/outputs/job_1/final_0.png",
            download_url: null,
            final_image_url: null
          }
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const created = await createGenerationJob({ userInput: "Create an ad", selectedReferenceTemplateId: "template_1" });
    const fetched = await getGenerationJob("job_1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:4000/api/generation-jobs");
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).selectedReferenceTemplateId).toBe("template_1");
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/generation-jobs/job_1");
    expect(created.job.result_payload?.schema_version).toBe("result_artifact_v1");
    expect(fetched.job.result_payload?.final_image_path).toBe("data/outputs/job_1/final_0.png");
  });
});
