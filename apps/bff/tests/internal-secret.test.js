import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApp } from "../src/app.js";

function jsonResponse(payload, init = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" }
  });
}

describe("internal secret forwarding", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("attaches X-EasyAds-Internal-Secret to orchestrator calls when configured", async () => {
    vi.stubEnv("EASYADS_INTERNAL_API_SECRET", "internal_secret_1");
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ jobId: "job_1", threadId: "thread_1", status: "queued" })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" }
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-EasyAds-Internal-Secret"]).toBe("internal_secret_1");
    await app.close();
  });

  it("omits the header when the secret is not configured", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ jobId: "job_1", threadId: "thread_1", status: "queued" })
    );
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    await app.inject({
      method: "POST",
      url: "/api/generate/chat/start",
      payload: { userInput: "우리 카페 딸기라떼 광고", renderProfile: "premium_api" }
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init.headers["X-EasyAds-Internal-Secret"]).toBeUndefined();
    await app.close();
  });
});
