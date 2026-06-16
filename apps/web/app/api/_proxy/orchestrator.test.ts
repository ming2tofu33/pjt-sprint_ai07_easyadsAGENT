import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxyOrchestratorBinary, proxyOrchestratorJson } from "./orchestrator";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("proxyOrchestratorJson", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("verifies Supabase bearer tokens and injects userId into generation job payloads", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1" });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "queued",
          progress: { progress_percent: 0, current_stage: "queued" },
          metadata: {}
        }
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({
        userInput: "햄버거 광고",
        runMode: "graph_job",
        userId: "spoofed_user",
        user_id: "spoofed_user_snake"
      })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenNthCalledWith(
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
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "햄버거 광고", runMode: "graph_job", userId: "user_uuid_1", accountType: "user" })
      })
    );
  });

  it("injects anonymous Supabase users as guest principals", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse({
        success: true,
        job: {
          job_id: "job_guest",
          status: "queued",
          progress: { progress_percent: 0, current_stage: "queued" },
          metadata: {}
        }
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer guest_access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({
        userInput: "게스트 광고",
        runMode: "graph_job",
        userId: "spoofed_user",
        accountType: "user"
      })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true,
      injectVerifiedUserIdHeader: true
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/generation-jobs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-EasyAds-User-Id": "guest_uuid_1",
          "X-EasyAds-Account-Type": "guest"
        }),
        body: JSON.stringify({
          userInput: "게스트 광고",
          runMode: "graph_job",
          userId: "guest_uuid_1",
          accountType: "guest"
        })
      })
    );
  });

  it("injects verified user headers for generation job GET routes", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockImplementation(async (_input: RequestInfo | URL, _init?: RequestInit) =>
        jsonResponse({ success: true, job: { job_id: "job_1", status: "queued", progress: {} } })
      );
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "guest_uuid_1", is_anonymous: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/generation-jobs/job_1", {
      headers: { authorization: "Bearer guest_access_token_1" }
    });
    await proxyOrchestratorJson(request, "GET", "/api/v1/generation-jobs/job_1", undefined, {
      injectVerifiedUserIdHeader: true
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://supabase.local/auth/v1/user",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          apikey: "anon",
          authorization: "Bearer guest_access_token_1"
        })
      })
    );
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(init.headers).toEqual(
      expect.objectContaining({
        "X-EasyAds-User-Id": "guest_uuid_1",
        "X-EasyAds-Account-Type": "guest"
      })
    );
  });

  it("removes spoofed user ids when no bearer token is present", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () =>
      jsonResponse({
        success: true,
        job: {
          job_id: "job_1",
          status: "waiting_user_input",
          progress: { progress_percent: 50, current_stage: "waiting_user_input" },
          metadata: {}
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs/job_1/answer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ field: "business_type", value: "cafe", userId: "spoofed_user", accountType: "guest" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs/job_1/answer", undefined, {
      injectVerifiedUserId: true
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/generation-jobs/job_1/answer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ field: "business_type", value: "cafe" })
      })
    );
  });

  it("returns a friendly 503 when auth is present but Supabase proxy config is missing", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({ userInput: "햄버거 광고", runMode: "graph_job" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true
    });
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(body.error_code).toBe("supabase_auth_configuration_missing");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns structured upstream diagnostics without exposing upstream internals", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "https://orchestrator.example.com");
    const logSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchMock = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = new NextRequest("http://localhost/api/generation-jobs", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-request-id": "req_web_1"
      },
      body: JSON.stringify({ userInput: "카페 아포가토 스토리 광고", runMode: "graph_job" })
    });

    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", undefined, {
      injectVerifiedUserId: true
    });
    const body = await response.json();

    expect(response.status).toBe(502);
    expect(body).toEqual(
      expect.objectContaining({
        error_code: "upstream_orchestrator_unavailable",
        request_id: "req_web_1"
      })
    );
    expect(body).not.toHaveProperty("upstream");
    expect(logSpy).toHaveBeenCalledWith(
      "Next BFF upstream request failed",
      expect.objectContaining({
        request_id: "req_web_1",
        error_code: "upstream_orchestrator_unavailable",
        upstream: {
          host: "orchestrator.example.com",
          path: "/api/v1/generation-jobs"
        }
      })
    );
  });

  it("generation job collection GET returns an explicit contract error", async () => {
    const route = await import("../generation-jobs/route");
    const response = await route.GET();
    const body = await response.json();

    expect(response.status).toBe(405);
    expect(body.error_code).toBe("generation_job_id_required");
    expect(body.message).toBe("GET /api/generation-jobs requires a job id.");
  });

  it("attaches the internal secret header to orchestrator requests when configured", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("EASYADS_INTERNAL_API_SECRET", "internal_secret_1");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/usage", { method: "GET" });
    await proxyOrchestratorJson(request, "GET", "/api/v1/usage");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-EasyAds-Internal-Secret"]).toBe("internal_secret_1");
  });

  it("omits the internal secret header when not configured", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/usage", { method: "GET" });
    await proxyOrchestratorJson(request, "GET", "/api/v1/usage");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-EasyAds-Internal-Secret"]).toBeUndefined();
  });

  it("supports DELETE requests", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/archive/items/a1", { method: "DELETE" });
    await proxyOrchestratorJson(request, "DELETE", "/api/v1/archive/items/a1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/archive/items/a1",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("injects verified guest principals into GET query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse({ success: true, threads: [] });
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/chat-threads?limit=10", {
      headers: { authorization: "Bearer guest_access_token_1" }
    });
    await proxyOrchestratorJson(request, "GET", "/api/v1/chat-threads", undefined, {
      injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" }
    });

    const targetUrl = new URL(String(fetchMock.mock.calls[1][0]));
    expect(`${targetUrl.origin}${targetUrl.pathname}`).toBe("http://orchestrator/api/v1/chat-threads");
    expect(targetUrl.searchParams.get("limit")).toBe("10");
    expect(targetUrl.searchParams.get("userId")).toBe("guest_uuid_1");
    expect(targetUrl.searchParams.get("accountType")).toBe("guest");
  });

  it("returns invalid_request when body schema validation fails", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const bodySchema = {
      safeParse: vi.fn(() => ({
        success: false,
        error: { issues: [{ path: ["name"], message: "Required" }] }
      }))
    };

    const request = new NextRequest("http://localhost/api/brand-kits", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "" })
    });
    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/brand-kits", undefined, { bodySchema });
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toBe("invalid_request");
    expect(bodySchema.safeParse).toHaveBeenCalledWith({ name: "" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns invalid_request when body schema validation fails for an empty POST body", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const bodySchema = {
      safeParse: vi.fn(() => ({
        success: false,
        error: { issues: [{ path: ["name"], message: "Required" }] }
      }))
    };

    const request = new NextRequest("http://localhost/api/brand-kits", {
      method: "POST",
      headers: { "content-type": "application/json" }
    });
    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/brand-kits", undefined, { bodySchema });
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toBe("invalid_request");
    expect(bodySchema.safeParse).toHaveBeenCalledWith(undefined);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns invalid_request when the request body contains malformed JSON", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const bodySchema = {
      safeParse: vi.fn(() => ({
        success: true,
        data: {}
      }))
    };

    const request = new NextRequest("http://localhost/api/brand-kits", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{not-valid-json"
    });
    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/brand-kits", undefined, { bodySchema });
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toBe("invalid_request");
    expect(bodySchema.safeParse).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("can override successful orchestrator response status", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/brand-kits", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "Cafe" })
    });
    const response = await proxyOrchestratorJson(request, "POST", "/api/v1/brand-kits", undefined, {
      successStatus: 201
    });

    expect(response.status).toBe(201);
  });

  it("injects verified user ids into request bodies with snake_case keys when requested", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "user_uuid_1" });
      }
      return jsonResponse({ success: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/legacy-action", {
      method: "POST",
      headers: {
        authorization: "Bearer access_token_1",
        "content-type": "application/json"
      },
      body: JSON.stringify({
        prompt: "New sale",
        userId: "spoofed_user",
        user_id: "spoofed_user_snake",
        accountType: "guest",
        account_type: "guest"
      })
    });
    await proxyOrchestratorJson(request, "POST", "/api/v1/legacy-action", undefined, {
      injectVerifiedUserIdSnakeBody: true
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://orchestrator/api/v1/legacy-action",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ prompt: "New sale", user_id: "user_uuid_1", account_type: "user" })
      })
    );
  });

  it("rejects routes that require a non-guest user when no bearer token is present", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/admin/references");
    const response = await proxyOrchestratorJson(request, "GET", "/api/v1/admin/references", undefined, {
      requireNonGuestUser: true
    });
    const body = await response.json();

    expect(response.status).toBe(401);
    expect(body.error_code).toBe("admin_session_required");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects routes that require a non-guest user when the session is anonymous", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://supabase.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon_key");
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).includes("/auth/v1/user")) {
        return jsonResponse({ id: "guest_uuid_1", is_anonymous: true });
      }
      return jsonResponse({ success: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/admin/references", {
      headers: { authorization: "Bearer guest_token_1" }
    });
    const response = await proxyOrchestratorJson(request, "GET", "/api/v1/admin/references", undefined, {
      requireNonGuestUser: true
    });
    const body = await response.json();

    expect(response.status).toBe(401);
    expect(body.error_code).toBe("admin_session_required");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("proxyOrchestratorBinary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("proxies binary GET responses and preserves content headers", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () =>
      new Response("image-bytes", {
        status: 200,
        headers: {
          "content-type": "image/png",
          "cache-control": "public, max-age=60"
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/assets/a1.png?download=1");
    const response = await proxyOrchestratorBinary(request, "/api/v1/assets/a1.png");

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("cache-control")).toBe("public, max-age=60");
    expect(await response.text()).toBe("image-bytes");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/assets/a1.png?download=1",
      expect.objectContaining({ method: "GET", cache: "no-store" })
    );
  });

  it("returns JSON for non-ok binary proxy responses", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ message: "Not found" }, { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/assets/missing.png");
    const response = await proxyOrchestratorBinary(request, "/api/v1/assets/missing.png");
    const body = await response.json();

    expect(response.status).toBe(404);
    expect(body.error_code).toBe("orchestrator_binary_proxy_error");
    expect(body.detail).toEqual({ message: "Not found" });
  });

  it("does not echo non-json binary error bodies", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () =>
      new Response("raw-error-secret", {
        status: 500,
        headers: { "content-type": "image/png" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/assets/broken.png");
    const response = await proxyOrchestratorBinary(request, "/api/v1/assets/broken.png");
    const body = await response.json();

    expect(response.status).toBe(500);
    expect(body.error_code).toBe("orchestrator_binary_proxy_error");
    expect(body.detail).toEqual({ content_type: "image/png" });
    expect(JSON.stringify(body)).not.toContain("raw-error-secret");
  });

  it("returns 502 JSON when binary proxy fetch fails", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const logSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const fetchMock = vi.fn(async () => {
      throw new Error("connection refused");
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new NextRequest("http://localhost/api/assets/a1.png");
    const response = await proxyOrchestratorBinary(request, "/api/v1/assets/a1.png");
    const body = await response.json();

    expect(response.status).toBe(502);
    expect(body.error_code).toBe("upstream_orchestrator_unavailable");
    expect(body).not.toHaveProperty("upstream");
    expect(logSpy).toHaveBeenCalledWith(
      "Next BFF upstream request failed",
      expect.objectContaining({
        request_id: null,
        error_code: "upstream_orchestrator_unavailable",
        upstream: {
          host: "orchestrator",
          path: "/api/v1/assets/a1.png"
        }
      })
    );
  });
});
