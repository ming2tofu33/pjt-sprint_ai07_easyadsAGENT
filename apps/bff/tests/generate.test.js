import { afterEach, describe, expect, it, vi } from "vitest";

import { buildApp } from "../src/app.js";

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
      payload: { userInput: "우리 카페 딸기라떼 광고" }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().jobId).toBe("job_1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "우리 카페 딸기라떼 광고" })
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
        selectedChannelId: "instagram-feed"
      }
    });

    expect(response.statusCode).toBe(200);
    expect(response.json().brief.copy).toBe("봄을 닮은 한 잔");
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://orchestrator/v1/marketing/chat/brief",
      expect.objectContaining({ method: "POST" })
    );
    await app.close();
  });
});
