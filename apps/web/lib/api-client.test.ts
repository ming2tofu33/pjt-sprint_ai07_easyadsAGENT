import { afterEach, describe, expect, it, vi } from "vitest";
import {
  answerGenerationJob,
  createBrandKit,
  createGenerationJob,
  deleteArchiveItem,
  fetchReferenceDetail,
  fetchReferences,
  fetchSimilarReferences,
  getBrandKit,
  getCurrentBrandKit,
  getGenerationJob,
  listReferenceTemplates,
  listArchiveItems,
  saveArchiveItem,
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
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
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

  it("shows a friendly message when the photo upload body is too large", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ message: "Request body is too large" }, { status: 413 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });

    await expect(uploadPhotoAsset(file)).rejects.toThrow("사진 용량이 너무 커요. 더 작은 사진으로 다시 시도해주세요.");
  });

  it("normalizes a trailing slash in the BFF base URL", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_BFF_BASE_URL", "https://bff.example.com/");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        type: "brief_ready",
        jobId: "job_trailing_slash",
        threadId: "thread_trailing_slash",
        status: "done",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "딸기라떼 출시",
          tone: "따뜻한",
          channel: "인스타 피드",
          imageDirection: "딸기라떼 중심",
          finalImagePath: "data/outputs/job_trailing_slash/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { startChatGeneration: startChatGenerationWithEnv } = await import("./api-client");

    await startChatGenerationWithEnv("딸기라떼 신메뉴 광고");

    expect(fetchMock.mock.calls[0][0]).toBe("https://bff.example.com/api/generate/chat/start");
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

  it("sends auto-pilot mode for chat and photo generation starts", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        type: "brief_ready",
        jobId: "job_auto_pilot",
        threadId: "thread_auto_pilot",
        status: "done",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await startChatGeneration("딸기라떼 신메뉴 광고", { copyGenerationMode: "auto_pilot" });
    await startPhotoGeneration({
      userInput: "이 사진으로 딸기라떼 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      copyGenerationMode: "auto_pilot"
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      userInput: "딸기라떼 신메뉴 광고",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "auto_pilot"
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      userInput: "이 사진으로 딸기라떼 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "auto_pilot"
    });
  });

  it("sends selected reference template ids for chat and photo generation starts", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        type: "brief_ready",
        jobId: "job_reference_template",
        threadId: "thread_reference_template",
        status: "done",
        context: { businessType: "카페", itemOrService: "수박주스", promotionGoal: "신메뉴 출시" },
        brief: {
          purpose: "신메뉴 출시",
          item: "수박주스",
          copy: "여름엔 수박주스",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "선택한 샘플 템플릿을 반영한 여름 음료 광고",
          finalImagePath: "data/outputs/job_reference_template/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await startChatGeneration("수박주스 신메뉴 광고", {
      copyGenerationMode: "auto_pilot",
      selectedReferenceTemplateId: "temp_watermelon_juice_feed"
    });
    await startPhotoGeneration({
      userInput: "이 사진으로 수박주스 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      copyGenerationMode: "auto_pilot",
      selectedReferenceTemplateId: "temp_watermelon_juice_feed"
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      userInput: "수박주스 신메뉴 광고",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "auto_pilot",
      selectedReferenceTemplateId: "temp_watermelon_juice_feed"
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      userInput: "이 사진으로 수박주스 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "auto_pilot",
      selectedReferenceTemplateId: "temp_watermelon_juice_feed"
    });
  });

  it("loads reference templates through the BFF and rewrites temporary asset URLs", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        items: [
          {
            template_id: "temp_watermelon_juice_feed",
            title: "수박주스 블루 여름 피드",
            description: "파란 배경과 큼직한 음료 중심의 여름 음료 샘플",
            category: "cafe",
            tags: ["수박", "여름"],
            business_types: ["cafe"],
            ad_formats: ["instagram_feed"],
            platforms: ["instagram"],
            aspect_ratio: "4:3",
            thumbnail_url: "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
            preview_url: "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
            style_keywords: ["summer", "blue"],
            color_palette: ["#5AB4F2", "#EF3B3B"],
            layout_hint: "top_large_headline_center_product_bottom_copy",
            typography_hint: "extra_bold_condensed_headline",
            popularity_score: 0.5,
            is_saved: false
          }
        ],
        pagination: { limit: 40, offset: 0, total: 1, has_more: false }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await listReferenceTemplates({ keyword: "수박 음료", tags: ["수박", "음료"], limit: 40 });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:4000/api/references?keyword=%EC%88%98%EB%B0%95+%EC%9D%8C%EB%A3%8C&tags=%EC%88%98%EB%B0%95&tags=%EC%9D%8C%EB%A3%8C&limit=40",
      expect.objectContaining({ method: "GET" })
    );
    expect(result.items[0]).toMatchObject({
      templateId: "temp_watermelon_juice_feed",
      title: "수박주스 블루 여름 피드",
      thumbnailUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
      previewUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png"
    });
    expect(result.pagination.total).toBe(1);
  });

  it("sends custom copy fields for chat and photo generation starts", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        type: "brief_ready",
        jobId: "job_custom_copy",
        threadId: "thread_custom_copy",
        status: "done",
        context: { businessType: "카페", itemOrService: "딸기라떼", promotionGoal: "신메뉴 출시" },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "오늘만 딸기라떼 반값",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await startChatGeneration("딸기라떼 신메뉴 광고", {
      copyGenerationMode: "custom_input",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
    });
    await startPhotoGeneration({
      userInput: "이 사진으로 딸기라떼 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      copyGenerationMode: "custom_input",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      userInput: "딸기라떼 신메뉴 광고",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "custom_input",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      userInput: "이 사진으로 딸기라떼 신메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png",
      adFormat: "instagram_feed",
      renderProfile: "premium_api",
      copyGenerationMode: "custom_input",
      userCustomHeadline: "오늘만 딸기라떼 반값",
      userCustomSubcopy: "오후 2시부터 5시까지"
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

describe("api-client backend contract routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("fetches reference catalog endpoints through the BFF", async () => {
    const rawTemplate = {
      template_id: "template_1",
      title: "샘플 템플릿",
      category: "cafe",
      tags: ["카페"],
      business_types: ["cafe"],
      ad_formats: ["instagram_feed"],
      platforms: ["instagram"],
      style_keywords: ["fresh"],
      color_palette: ["#FFFFFF"],
      popularity_score: 0.5,
      is_saved: false
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/references/template_1")) {
        return jsonResponse({ success: true, template: rawTemplate, detail: {}, similar_templates: [rawTemplate] });
      }
      if (url.includes("/api/references/template_1/similar")) {
        return jsonResponse({ success: true, template_id: "template_1", items: [rawTemplate] });
      }
      return jsonResponse({ success: true, items: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchReferences({ category: "cafe", tags: ["CTA", "warm"], limit: 2 });
    const detail = await fetchReferenceDetail("template_1");
    const similar = await fetchSimilarReferences("template_1", { limit: 3 });

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:4000/api/references?category=cafe&tags=CTA&tags=warm&limit=2");
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/references/template_1");
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://127.0.0.1:4000/api/references/template_1/similar?limit=3");
    expect(detail.template.templateId).toBe("template_1");
    expect(detail.similarTemplates[0].templateId).toBe("template_1");
    expect(similar.items[0].templateId).toBe("template_1");
  });

  it("calls brand kit endpoints through the BFF", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ success: true }));
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
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
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

    const created = await createGenerationJob({ userInput: "Create an ad" });
    const fetched = await getGenerationJob("job_1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:4000/api/generation-jobs");
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/generation-jobs/job_1");
    expect(created.job.result_payload?.schema_version).toBe("result_artifact_v1");
    expect(fetched.job.result_payload?.final_image_path).toBe("data/outputs/job_1/final_0.png");
  });

  it("answers generation job questions through the BFF", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed" },
          metadata: { execution_mode: "graph_execution" }
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await answerGenerationJob("job_1", {
      field: "business_type",
      value: "cafe",
      customText: undefined
    });

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:4000/api/generation-jobs/job_1/answer");
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ field: "business_type", value: "cafe" })
      })
    );
    expect(response.job.status).toBe("done");
  });

  it("calls archive endpoints through the BFF and maps response fields", async () => {
    vi.doMock("./supabase/browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: { access_token: "access_token_1" } } })
        }
      })
    }));
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse({
          success: true,
          item: {
            ad_id: "archive_1",
            job_id: "job_1",
            title: "봄을 닮은 한 잔",
            image_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            thumbnail_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            status: "saved",
            ad_format: "1:1",
            platform: "인스타 피드",
            source: "generated",
            saved_at: "2026-06-04T00:00:00+00:00",
            metadata: { tags: ["카페"] }
          }
        });
      }
      if (init?.method === "DELETE") {
        return jsonResponse({
          success: true,
          item: {
            ad_id: "archive_1",
            title: "봄을 닮은 한 잔",
            status: "saved",
            source: "generated"
          }
        });
      }
      return jsonResponse({
        success: true,
        items: [
          {
            ad_id: "archive_1",
            job_id: "job_1",
            title: "봄을 닮은 한 잔",
            status: "saved",
            source: "generated"
          }
        ],
        pagination: { limit: 20, offset: 0, total: 1, has_more: false }
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const saved = await saveArchiveItem({
      title: "봄을 닮은 한 잔",
      publicJobId: "job_1",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
      adFormat: "1:1",
      platform: "인스타 피드",
      metadata: { tags: ["카페"] }
    });
    const listed = await listArchiveItems({ limit: 20 });
    const deleted = await deleteArchiveItem("archive_1");

    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:4000/api/archive/items");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      title: "봄을 닮은 한 잔",
      publicJobId: "job_1",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
      status: "saved",
      source: "generated"
    });
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://127.0.0.1:4000/api/archive/items?limit=20");
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://127.0.0.1:4000/api/archive/items/archive_1");
    expect(fetchMock.mock.calls[0][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer access_token_1" })
    );
    expect(fetchMock.mock.calls[1][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer access_token_1" })
    );
    expect(fetchMock.mock.calls[2][1]?.headers).toEqual(
      expect.objectContaining({ authorization: "Bearer access_token_1" })
    );
    expect(saved.item.adId).toBe("archive_1");
    expect(saved.item.savedAt).toBe("2026-06-04T00:00:00+00:00");
    expect(listed.items[0].jobId).toBe("job_1");
    expect(deleted.item.adId).toBe("archive_1");
  });
});
