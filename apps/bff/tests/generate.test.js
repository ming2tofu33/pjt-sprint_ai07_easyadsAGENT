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
      payload: {
        userInput: "우리 카페 딸기라떼 광고",
        renderProfile: "premium_api",
        referenceImagePath: "data/uploads/reference_1.png"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().jobId).toBe("job_1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          userInput: "우리 카페 딸기라떼 광고",
          renderProfile: "premium_api",
          referenceImagePath: "data/uploads/reference_1.png"
        })
      })
    );
    await app.close();
  });

  it("proxies reference template list and temporary assets to the orchestrator", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/temp-assets/")) {
        if (String(url).endsWith("/fallback-only.png")) {
          return new Response(Buffer.from("image bytes"), {
            status: 200,
            headers: { "content-type": "image/png" }
          });
        }
        return new Response(Buffer.from("image bytes"), {
          status: 200,
          headers: {
            "content-type": "image/png",
            "cache-control": "public, max-age=604800, immutable"
          }
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
    const fallbackAssetResponse = await app.inject({
      method: "GET",
      url: "/api/references/temp-assets/2026-06-user-refs/fallback-only.png"
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
    expect(fallbackAssetResponse.statusCode).toBe(200);
    expect(similarResponse.statusCode).toBe(200);
    expect(assetResponse.headers["content-type"]).toContain("image/png");
    expect(assetResponse.headers["cache-control"]).toBe("public, max-age=604800, immutable");
    expect(fallbackAssetResponse.headers["cache-control"]).toBe("public, max-age=604800, immutable");
    expect(assetResponse.body).toBe("image bytes");
    expect(fallbackAssetResponse.body).toBe("image bytes");
    await app.close();
  });


  it("proxies asset uploads and admin reference creation", async () => {
    const fetchImpl = vi.fn(async (url, init) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "admin_user_1" });
      }
      if (String(url).endsWith("/assets/uploads/presign?user_id=admin_user_1&account_type=user")) {
        return jsonResponse({ asset: { asset_id: "asset_abc", kind: "reference", status: "pending" }, upload: { method: "PUT", url: "https://r2.example.com/upload" } });
      }
      if (String(url).includes("/assets/uploads/asset_abc/complete")) {
        return jsonResponse({ success: true, asset: { assetId: "asset_abc", kind: "reference", status: "ready" } });
      }
      return jsonResponse({
        template: {
          template_id: "ref_admin",
          title: "관리자 샘플",
          category: "cafe",
          tags: [],
          business_types: ["cafe"],
          ad_formats: ["instagram_feed"],
          platforms: ["instagram"],
          style_keywords: [],
          color_palette: [],
          popularity_score: 0
        }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    await app.inject({
      method: "POST",
      url: "/api/assets/uploads/presign",
      headers: { authorization: "Bearer access_token_1" },
      payload: { kind: "reference", filename: "ref.png", mimeType: "image/png", sizeBytes: 3 }
    });
    await app.inject({
      method: "POST",
      url: "/api/assets/uploads/asset_abc/complete",
      headers: { authorization: "Bearer access_token_1" }
    });
    await app.inject({
      method: "POST",
      url: "/api/admin/references",
      headers: { authorization: "Bearer access_token_1" },
      payload: { assetId: "asset_abc", title: "관리자 샘플", category: "cafe", businessTypes: ["cafe"] }
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(2, "http://orchestrator/api/v1/assets/uploads/presign?user_id=admin_user_1&account_type=user", expect.objectContaining({ method: "POST" }));
    expect(fetchImpl).toHaveBeenNthCalledWith(4, "http://orchestrator/api/v1/assets/uploads/asset_abc/complete?user_id=admin_user_1&account_type=user", expect.objectContaining({ method: "POST" }));
    expect(fetchImpl).toHaveBeenNthCalledWith(6, "http://orchestrator/api/v1/admin/references?user_id=admin_user_1", expect.objectContaining({ method: "POST" }));
    await app.close();
  });

  it("forwards anonymous account type for asset uploads and chat threads", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      if (String(url).includes("/assets/uploads/presign")) {
        return jsonResponse({ asset: { asset_id: "asset_guest", kind: "source", status: "pending" }, upload: { method: "PUT", url: "https://r2.example.com/upload" } });
      }
      return jsonResponse({ threads: [], total: 0 });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const assetResponse = await app.inject({
      method: "POST",
      url: "/api/assets/uploads/presign",
      headers: { authorization: "Bearer guest_access_token_1" },
      payload: { kind: "source", filename: "source.png", mimeType: "image/png", sizeBytes: 1024 }
    });
    const chatResponse = await app.inject({
      method: "GET",
      url: "/api/chat-threads?include_archived=true",
      headers: { authorization: "Bearer guest_access_token_1" }
    });

    expect(assetResponse.statusCode).toBe(200);
    expect(chatResponse.statusCode).toBe(200);
    const assetUrl = new URL(fetchImpl.mock.calls[1][0]);
    expect(assetUrl.searchParams.get("user_id")).toBe("guest_uuid_1");
    expect(assetUrl.searchParams.get("account_type")).toBe("guest");
    const chatUrl = new URL(fetchImpl.mock.calls[3][0]);
    expect(chatUrl.searchParams.get("include_archived")).toBe("true");
    expect(chatUrl.searchParams.get("userId")).toBe("guest_uuid_1");
    expect(chatUrl.searchParams.get("accountType")).toBe("guest");
    await app.close();
  });

  it("rejects anonymous Supabase sessions for admin reference creation", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_user_1", is_anonymous: true });
      }
      return jsonResponse({ success: true });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/admin/references",
      headers: { authorization: "Bearer anon_access_token_1" },
      payload: { assetId: "asset_abc", title: "관리자 샘플", category: "cafe", businessTypes: ["cafe"] }
    });

    expect(response.statusCode).toBe(401);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl.mock.calls[0][0]).toBe("https://supabase.example.com/auth/v1/user");
    expect(fetchImpl.mock.calls.some(([url]) => String(url).includes("/api/v1/admin/references"))).toBe(false);
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

  it("proxies archive list, detail, update, and delete requests", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ success: true, items: [], pagination: { limit: 20, offset: 0, total: 0, has_more: false } }));
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({ method: "GET", url: "/api/archive/items?limit=20" });
    await app.inject({ method: "GET", url: "/api/archive/items/archive_1" });
    await app.inject({ method: "PATCH", url: "/api/archive/items/archive_1", payload: { status: "favorite" } });
    await app.inject({ method: "DELETE", url: "/api/archive/items/archive_1" });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/api/v1/archive/items?limit=20",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/archive/items/archive_1",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://orchestrator/api/v1/archive/items/archive_1",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "favorite" }) })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      4,
      "http://orchestrator/api/v1/archive/items/archive_1",
      expect.objectContaining({ method: "DELETE" })
    );
    await app.close();
  });

  it("archives chat threads through the orchestrator", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        success: true,
        thread: {
          thread_id: "thread_1",
          title: "딸기라떼 광고",
          status: "archived",
          final_brief: {},
          active_job_id: null,
          has_final_output: false,
          last_message_at: "2026-06-07T00:00:00+00:00",
          archived_at: "2026-06-07T00:00:00+00:00",
          created_at: "2026-06-07T00:00:00+00:00",
          updated_at: "2026-06-07T00:00:00+00:00"
        }
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/chat-threads/thread_1/archive"
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().thread.status).toBe("archived");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/chat-threads/thread_1/archive",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({})
      })
    );
    await app.close();
  });

  it("verifies Supabase sessions before forwarding archive user ids", async () => {
    const fetchImpl = vi.fn(async (url, init) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", email: "owner@example.com" });
      }
      return jsonResponse(
        {
          success: true,
          item: {
            ad_id: "archive_1",
            title: "봄을 닮은 한 잔",
            status: "saved",
            source: "generated"
          }
        },
        { status: init?.method === "POST" ? 201 : 200 }
      );
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/archive/items",
      headers: { authorization: "Bearer access_token_1" },
      payload: {
        title: "봄을 닮은 한 잔",
        publicJobId: "job_1",
        userId: "spoofed_user"
      }
    });
    const detailResponse = await app.inject({
      method: "GET",
      url: "/api/archive/items/archive_1",
      headers: { authorization: "Bearer access_token_1" }
    });
    const patchResponse = await app.inject({
      method: "PATCH",
      url: "/api/archive/items/archive_1",
      headers: { authorization: "Bearer access_token_1" },
      payload: { status: "favorite" }
    });

    expect(response.statusCode).toBe(201);
    expect(detailResponse.statusCode).toBe(200);
    expect(patchResponse.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://supabase.example.com/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon_key",
          authorization: "Bearer access_token_1"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/archive/items",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "봄을 닮은 한 잔",
          public_job_id: "job_1",
          status: "saved",
          user_id: "user_uuid_1",
          account_type: "user"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      4,
      "http://orchestrator/api/v1/archive/items/archive_1?user_id=user_uuid_1&account_type=user",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      6,
      "http://orchestrator/api/v1/archive/items/archive_1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "favorite", user_id: "user_uuid_1", account_type: "user" })
      })
    );
    await app.close();
  });

  it("uses anonymous Supabase user ids for archive list scope", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse({
        items: [],
        pagination: { limit: 20, offset: 0, total: 0, has_more: false }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "GET",
      url: "/api/archive/items?limit=20",
      headers: { authorization: "Bearer guest_access_token_1" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/archive/items?limit=20&user_id=guest_uuid_1&account_type=guest",
      expect.objectContaining({ method: "GET" })
    );
    await app.close();
  });

  it("rejects invalid archive authorization headers", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ id: "user_uuid_1" }));
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "GET",
      url: "/api/archive/items",
      headers: { authorization: "not-a-bearer-token" }
    });

    expect(response.statusCode).toBe(401);
    expect(fetchImpl).not.toHaveBeenCalled();
    await app.close();
  });

  it("proxies generation job create and get requests", async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      if (init?.method === "GET") {
        return jsonResponse({
          success: true,
          job: {
            job_id: "job_1",
            thread_id: "thread_1",
            status: "queued",
            progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
            metadata: { workspace_id: "workspace_1" }
          }
        });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          thread_id: "thread_1",
          status: "queued",
          progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
          metadata: { workspace_id: "workspace_1" }
        }
      });
    });
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const createResponse = await app.inject({
      method: "POST",
      url: "/api/generation-jobs",
      payload: {
        userInput: "Supabase 연결 확인",
        runMode: "queued_only",
        selectedReferenceTemplateId: "seed_1",
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "깔끔한",
        customDirection: "제품을 크게",
        userCustomHeadline: "오늘만 반값",
        userCustomSubcopy: "오후 5시까지"
      }
    });
    const getResponse = await app.inject({
      method: "GET",
      url: "/api/generation-jobs/job_1"
    });

    expect(createResponse.statusCode).toBe(200);
    expect(getResponse.statusCode).toBe(200);
    expect(getResponse.json().job.job_id).toBe("job_1");
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          userInput: "Supabase 연결 확인",
          runMode: "queued_only",
          selectedReferenceTemplateId: "seed_1",
          selectedCopyId: "copy_1",
          selectedChannelId: "instagram-feed",
          selectedTone: "깔끔한",
          customDirection: "제품을 크게",
          userCustomHeadline: "오늘만 반값",
          userCustomSubcopy: "오후 5시까지"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs/job_1",
      expect.objectContaining({ method: "GET" })
    );
    await app.close();
  });

  it("verifies Supabase sessions before forwarding generation job user ids", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", email: "owner@example.com" });
      }
      return jsonResponse(
        {
          success: true,
          job: {
            job_id: "job_1",
            thread_id: "thread_1",
            status: "queued",
            progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
            metadata: { workspace_id: "workspace_1" }
          }
        },
        { status: 201 }
      );
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs",
      headers: { authorization: "Bearer access_token_1" },
      payload: {
        userInput: "로그인 사용자 작업방 생성",
        runMode: "queued_only",
        userId: "spoofed_user"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://supabase.example.com/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon_key",
          authorization: "Bearer access_token_1"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-EasyAds-User-Id": "user_uuid_1",
          "X-EasyAds-Account-Type": "user"
        }),
        body: JSON.stringify({
          userInput: "로그인 사용자 작업방 생성",
          runMode: "queued_only",
          userId: "user_uuid_1",
          accountType: "user"
        })
      })
    );
    await app.close();
  });

  it("forwards anonymous Supabase users as guest generation principals", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse(
        {
          success: true,
          job: {
            job_id: "job_guest_1",
            thread_id: "thread_guest_1",
            status: "queued",
            progress: { progress_percent: 0, current_stage: "queued", stage_order: [] },
            metadata: { account_type: "guest" }
          }
        },
        { status: 201 }
      );
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs",
      headers: { authorization: "Bearer guest_access_token_1" },
      payload: {
        userInput: "게스트 광고 생성",
        runMode: "queued_only"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-EasyAds-User-Id": "guest_uuid_1",
          "X-EasyAds-Account-Type": "guest"
        }),
        body: JSON.stringify({
          userInput: "게스트 광고 생성",
          runMode: "queued_only",
          userId: "guest_uuid_1",
          accountType: "guest"
        })
      })
    );
    await app.close();
  });

  it("verifies Supabase sessions before forwarding generation job reads", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", email: "owner@example.com" });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "queued",
          progress: { progress_percent: 0, current_stage: "queued", stage_order: [] }
        }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "GET",
      url: "/api/generation-jobs/job_1",
      headers: { authorization: "Bearer access_token_1" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs/job_1",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-EasyAds-User-Id": "user_uuid_1" })
      })
    );
    await app.close();
  });

  it("proxies generation job answers to the orchestrator", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed", stage_order: [] },
          metadata: { execution_mode: "graph_execution" }
        }
      })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs/job_1/answer",
      payload: { field: "business_type", value: "cafe" }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().job.status).toBe("done");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/generation-jobs/job_1/answer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ field: "business_type", value: "cafe" })
      })
    );
    await app.close();
  });

  it("verifies Supabase sessions before forwarding generation job answers", async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1", email: "owner@example.com" });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed", stage_order: [] },
          metadata: { execution_mode: "graph_execution" }
        }
      });
    });
    const app = buildApp({
      orchestratorBaseUrl: "http://orchestrator",
      fetchImpl,
      supabaseUrl: "https://supabase.example.com",
      supabaseAnonKey: "anon_key"
    });

    const response = await app.inject({
      method: "POST",
      url: "/api/generation-jobs/job_1/answer",
      headers: { authorization: "Bearer access_token_1" },
      payload: { field: "business_type", value: "restaurant", userId: "spoofed_user" }
    });

    expect(response.statusCode).toBe(200);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://supabase.example.com/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon_key",
          authorization: "Bearer access_token_1"
        })
      })
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs/job_1/answer",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-EasyAds-User-Id": "user_uuid_1" }),
        body: JSON.stringify({ field: "business_type", value: "restaurant", userId: "user_uuid_1" })
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

  it("accepts phone-sized JSON photo uploads larger than the previous body limit", async () => {
    const uploadDir = await fs.mkdtemp(path.join(os.tmpdir(), "easyads-upload-large-"));
    const app = buildApp({ fetchImpl: vi.fn(), uploadDir });
    const imageBytes = Buffer.alloc(20 * 1024 * 1024, 7);
    const dataUrl = `data:image/png;base64,${imageBytes.toString("base64")}`;

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/photo/upload",
      payload: {
        filename: "large-menu.png",
        mimeType: "image/png",
        dataUrl
      }
    });

    expect(response.statusCode).toBe(200);
    const payload = response.json();
    expect(payload.sizeBytes).toBe(imageBytes.length);
    await expect(fs.stat(path.join(uploadDir, path.basename(payload.sourceImagePath)))).resolves.toMatchObject({ size: imageBytes.length });
    await app.close();
    await fs.rm(uploadDir, { recursive: true, force: true });
  }, 20_000);

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
          imageDirection: "선택한 샘플 템플릿을 반영한 여름 음료 광고",
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
