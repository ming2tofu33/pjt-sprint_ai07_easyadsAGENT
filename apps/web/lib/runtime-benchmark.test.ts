import fs from "node:fs";
import path from "node:path";

import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createGenerationJob,
  getGenerationJob,
  listArchiveItems,
  listReferenceTemplates,
  recordRenderMark
} from "./api-client";
import { exportWebPerfEvents, resetWebPerfEvents, setWebPerfContext } from "./performance";
import { proxyOrchestratorJson } from "@/app/api/_proxy/orchestrator";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

async function runDashboardScenario() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/archive")) {
      return jsonResponse({ items: [], pagination: { limit: 20, offset: 0, total: 0, hasMore: false } });
    }
    return jsonResponse({ items: [], pagination: { limit: 20, offset: 0, total: 0, hasMore: false } });
  });
  vi.stubGlobal("fetch", fetchMock);
  recordRenderMark("shell_rendered");
  await listArchiveItems();
  await listReferenceTemplates();
  recordRenderMark("all_required_data_rendered");
  return {
    request_count: fetchMock.mock.calls.length,
  };
}

async function runPollingScenario() {
  let pollCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "POST") {
      return jsonResponse({ success: true, job: { job_id: "job_1", thread_id: "thread_1", status: "queued" } });
    }
    if (url.includes("/api/v1/generation-jobs/job_1")) {
      pollCount += 1;
      const status = pollCount >= 3 ? "done" : "running";
      return jsonResponse({ success: true, job: { job_id: "job_1", thread_id: "thread_1", status } });
    }
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  recordRenderMark("polling_started");
  await createGenerationJob({ userInput: "bench", runMode: "graph_job" });
  for (let index = 0; index < 3; index += 1) {
    await getGenerationJob("job_1");
    recordRenderMark(`poll_iteration_${index + 1}`);
  }
  recordRenderMark("final_result_visible");
  return { poll_count: pollCount };
}

async function runBffScenario() {
  vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
  vi.stubEnv("SUPABASE_URL", "http://supabase.local");
  vi.stubEnv("SUPABASE_ANON_KEY", "anon");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/auth/v1/user")) {
      return jsonResponse({ id: "user_1" });
    }
    return jsonResponse({ success: true, items: [] });
  });
  vi.stubGlobal("fetch", fetchMock);
  const request = new NextRequest("http://localhost/api/archive", {
    method: "GET",
    headers: { authorization: "Bearer token" }
  });
  const response = await proxyOrchestratorJson(request, "GET", "/api/v1/archive", undefined, {
    injectVerifiedUserIdHeader: true
  });
  return {
    server_timing: response.headers.get("Server-Timing"),
    auth_calls: response.headers.get("X-EasyAds-Bff-Auth-Calls"),
    auth_network: response.headers.get("X-EasyAds-Bff-Auth-Network"),
    auth_dedup_hits: response.headers.get("X-EasyAds-Bff-Auth-Dedup-Hits"),
  };
}

describe("runtime benchmark harness", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("writes runtime benchmark output", async () => {
    vi.stubEnv("NEXT_PUBLIC_EASYADS_PERF_TRACE", "1");
    vi.stubEnv("EASYADS_PERF_TRACE", "1");
    resetWebPerfEvents();
    setWebPerfContext({
      schema_version: 1,
      trace_id: "trace_bench",
      request_id: "req_bench",
      scenario_id: process.env.EASYADS_RUNTIME_BENCH_SCENARIO ?? "A",
      run_id: process.env.EASYADS_RUNTIME_BENCH_RUN_ID ?? "run_1",
      cold_or_warm: process.env.EASYADS_RUNTIME_BENCH_COLD_WARM ?? "cold",
      component: "web",
      operation: "runtime_benchmark",
      started_at: new Date().toISOString(),
      duration_ms: 0,
      status: "ok",
      metadata: {}
    });

    const scenario = process.env.EASYADS_RUNTIME_BENCH_SCENARIO ?? "A";
    const dashboard = await runDashboardScenario();
    const polling = await runPollingScenario();
    const bff = await runBffScenario();
    const events = exportWebPerfEvents();
    const outputPath = process.env.EASYADS_RUNTIME_BENCH_OUTPUT;
    if (outputPath) {
      fs.mkdirSync(path.dirname(outputPath), { recursive: true });
      fs.writeFileSync(
        outputPath,
        JSON.stringify({ scenario, dashboard, polling, bff, events }, null, 2),
        "utf-8"
      );
    }
    expect(events.length).toBeGreaterThan(0);
  });
});
