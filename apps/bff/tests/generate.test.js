import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApp, DEFAULT_UPLOAD_DIR } from "../src/app.js";

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

  it("proxies reference template list and temporary assets to the orchestrator", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/temp-assets/")) {
        return new Response(Buffer.from("image bytes"), {
          status: 200,
          headers: { "content-type": "image/png" }
        });
      }
      return jsonResponse({
        success: true,
        items: [
          {
            template_id: "temp_watermelon_juice_feed",
            title: "수박주스 블루 여름 피드",
            category: "cafe",
            tags: ["수박", "여름"],
            business_types: ["cafe"],
            ad_formats: ["instagram_feed"],
            platforms: ["instagram"],
            thumbnail_url: "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
            preview_url: "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
            style_keywords: ["summer", "blue"],
            color_palette: ["#5AB4F2", "#EF3B3B"],
            popularity_score: 0.5,
            is_saved: false
          }
        ],
        pagination: { limit: 20, offset: 0, total: 1, has_more: false }
      });
    });
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const listResponse = await app.inject({
      method: "GET",
      url: "/api/references?keyword=%EC%88%98%EB%B0%95"
    });
    const assetResponse = await app.inject({
      method: "GET",
      url: "/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png"
    });
    const similarResponse = await app.inject({
      method: "GET",
      url: "/api/references/temp_watermelon_juice_feed/similar?limit=3"
    });

    expect(listResponse.statusCode).toBe(200);
    expect(listResponse.json().items[0].template_id).toBe("temp_watermelon_juice_feed");
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/api/v1/references?keyword=%EC%88%98%EB%B0%95",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://orchestrator/api/v1/references/temp_watermelon_juice_feed/similar?limit=3",
      expect.objectContaining({ method: "GET" })
    );
    expect(assetResponse.statusCode).toBe(200);
    expect(similarResponse.statusCode).toBe(200);
    expect(assetResponse.headers["content-type"]).toContain("image/png");
    expect(assetResponse.body).toBe("image bytes");
    await app.close();
  });

  it("proxies archive item saves with normalized payload fields", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        {
          success: true,
          item: {
            ad_id: "archive_1",
            job_id: "job_1",
            title: "봄을 닮은 한 잔",
            image_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            status: "saved",
            source: "generated",
            metadata: { tags: ["카페"] }
          }
        },
        { status: 201 }
      )
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/archive/items",
      payload: {
        title: "봄을 닮은 한 잔",
        publicJobId: "job_1",
        imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        thumbnailUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        adFormat: "1:1",
        platform: "인스타 피드",
        source: "generated",
        metadata: { tags: ["카페"] }
      }
    });

    expect(response.statusCode).toBe(201);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/archive/items",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "봄을 닮은 한 잔",
          public_job_id: "job_1",
          image_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
          thumbnail_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
          status: "saved",
          ad_format: "1:1",
          platform: "인스타 피드",
          source: "generated",
          metadata: { tags: ["카페"] }
        })
      })
    );
    await app.close();
  });

  it("proxies archive list and delete requests", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ success: true, items: [], pagination: { limit: 20, offset: 0, total: 0, has_more: false } }));
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({ method: "GET", url: "/api/archive/items?limit=20" });
    await app.inject({ method: "DELETE", url: "/api/archive/items/archive_1" });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/api/v1/archive/items?limit=20",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/archive/items/archive_1",
      expect.objectContaining({ method: "DELETE" })
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

  it("uses the repo data/uploads directory by default", async () => {
    const app = buildApp({ fetchImpl: vi.fn() });
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
    const savedPath = path.join(DEFAULT_UPLOAD_DIR, path.basename(payload.sourceImagePath));
    await expect(fs.readFile(savedPath)).resolves.toEqual(Buffer.from("fake image bytes"));
    await app.close();
    await fs.rm(savedPath, { force: true });
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

  it("passes no-copy mode through generation start requests", async () => {
    const fetchImpl = vi.fn(async () =>
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
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: {
        userInput: "딸기라떼 이미지만 만들어줘",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "no_copy"
      }
    });
    await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "이 사진으로 이미지만 만들어줘",
        sourceImagePath: "data/uploads/photo_abc.png",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "no_copy"
      }
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "딸기라떼 이미지만 만들어줘",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "no_copy"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/v1/marketing/photo/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "이 사진으로 이미지만 만들어줘",
          sourceImagePath: "data/uploads/photo_abc.png",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "no_copy"
        })
      })
    );
    await app.close();
  });

  it("passes auto-pilot mode through generation start requests", async () => {
    const fetchImpl = vi.fn(async () =>
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
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: {
        userInput: "딸기라떼 신메뉴 인스타 피드 광고",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "auto_pilot"
      }
    });
    await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "이 사진으로 딸기라떼 신메뉴 인스타 피드 광고",
        sourceImagePath: "data/uploads/photo_abc.png",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "auto_pilot"
      }
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "딸기라떼 신메뉴 인스타 피드 광고",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "auto_pilot"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/v1/marketing/photo/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "이 사진으로 딸기라떼 신메뉴 인스타 피드 광고",
          sourceImagePath: "data/uploads/photo_abc.png",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "auto_pilot"
        })
      })
    );
    await app.close();
  });

  it("passes selected reference template ids through generation start requests", async () => {
    const fetchImpl = vi.fn(async () =>
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
          imageDirection: "선택한 레퍼런스 템플릿을 반영한 여름 음료 광고",
          finalImagePath: "data/outputs/job_reference_template/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: {
        userInput: "수박주스 신메뉴 광고",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "auto_pilot",
        selectedReferenceTemplateId: "temp_watermelon_juice_feed"
      }
    });
    await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "이 사진으로 수박주스 신메뉴 광고",
        sourceImagePath: "data/uploads/photo_abc.png",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "auto_pilot",
        selectedReferenceTemplateId: "temp_watermelon_juice_feed"
      }
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body).selectedReferenceTemplateId).toBe("temp_watermelon_juice_feed");
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body).selectedReferenceTemplateId).toBe("temp_watermelon_juice_feed");
    await app.close();
  });

  it("passes custom copy fields through generation start requests", async () => {
    const fetchImpl = vi.fn(async () =>
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
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경",
          finalImagePath: "data/outputs/job_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: {
        userInput: "딸기라떼 신메뉴 인스타 피드 광고",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "custom_input",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      }
    });
    await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "이 사진으로 딸기라떼 신메뉴 인스타 피드 광고",
        sourceImagePath: "data/uploads/photo_abc.png",
        adFormat: "instagram_feed",
        renderProfile: "premium_api",
        copyGenerationMode: "custom_input",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      }
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "딸기라떼 신메뉴 인스타 피드 광고",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "custom_input",
          userCustomHeadline: "오늘만 딸기라떼 반값",
          userCustomSubcopy: "오후 2시부터 5시까지"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/v1/marketing/photo/start",
      expect.objectContaining({
        body: JSON.stringify({
          userInput: "이 사진으로 딸기라떼 신메뉴 인스타 피드 광고",
          sourceImagePath: "data/uploads/photo_abc.png",
          adFormat: "instagram_feed",
          renderProfile: "premium_api",
          copyGenerationMode: "custom_input",
          userCustomHeadline: "오늘만 딸기라떼 반값",
          userCustomSubcopy: "오후 2시부터 5시까지"
        })
      })
    );
    await app.close();
  });
});
