import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxyOrchestratorJson } from "./orchestrator";

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
});
