import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers }
  });
}

describe("generate chat and photo Next routes", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("proxies chat start to the standard marketing chat endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ jobId: "job_1", threadId: "thread_1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./start/route");

    const response = await POST(
      new NextRequest("http://localhost/api/generate/chat/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ userInput: "카페 광고" })
      })
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/chat/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ userInput: "카페 광고" })
      })
    );
  });

  it("rejects custom copy without a headline before proxying chat start", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./start/route");

    const response = await POST(
      new NextRequest("http://localhost/api/generate/chat/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ userInput: "광고", copyGenerationMode: "custom_input" })
      })
    );
    const body = await response.json();

    expect(response.status).toBe(400);
    expect(body.error).toBe("invalid_request");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("proxies chat brief selections to the standard marketing brief endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./brief/route");

    const payload = {
      jobId: "job_1",
      threadId: "thread_1",
      selectedCopyId: "copy_1",
      selectedChannelId: "instagram_feed"
    };
    const response = await POST(
      new NextRequest("http://localhost/api/generate/chat/brief", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/chat/brief",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("keeps canonical channel ids intact when proxying chat brief selections", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./brief/route");

    const payload = {
      jobId: "job_banner",
      threadId: "thread_banner",
      selectedCopyId: "copy_banner",
      selectedChannelId: "banner"
    };

    await POST(
      new NextRequest("http://localhost/api/generate/chat/brief", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/chat/brief",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("proxies chat answers to the standard marketing answer endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./answer/route");

    const payload = {
      jobId: "job_1",
      threadId: "thread_1",
      field: "business_type",
      value: "cafe"
    };
    const response = await POST(
      new NextRequest("http://localhost/api/generate/chat/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/chat/answer",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("passes selectedChannelId through in copy-candidate, option-question, and brief-ready responses", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ type: "copy_candidates", jobId: "job_banner", threadId: "thread_banner", selectedChannelId: "banner" }))
      .mockResolvedValueOnce(jsonResponse({ type: "option_question", jobId: "job_banner", threadId: "thread_banner", selectedChannelId: "banner" }))
      .mockResolvedValueOnce(jsonResponse({ type: "brief_ready", jobId: "job_banner", threadId: "thread_banner", selectedChannelId: "banner" }));
    vi.stubGlobal("fetch", fetchMock);
    const startRoute = await import("./start/route");
    const answerRoute = await import("./answer/route");

    const copyResponse = await startRoute.POST(
      new NextRequest("http://localhost/api/generate/chat/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ userInput: "배너 광고" })
      })
    );
    const questionResponse = await answerRoute.POST(
      new NextRequest("http://localhost/api/generate/chat/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jobId: "job_banner", threadId: "thread_banner", field: "business_type", value: "cafe" })
      })
    );
    const briefResponse = await answerRoute.POST(
      new NextRequest("http://localhost/api/generate/chat/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jobId: "job_banner", threadId: "thread_banner", field: "promotion_goal", value: "new_launch" })
      })
    );

    expect((await copyResponse.json()).selectedChannelId).toBe("banner");
    expect((await questionResponse.json()).selectedChannelId).toBe("banner");
    expect((await briefResponse.json()).selectedChannelId).toBe("banner");
  });

  it("proxies photo start to the standard marketing photo endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ jobId: "job_photo_1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("../photo/start/route");

    const payload = {
      userInput: "사진으로 메뉴 광고",
      sourceAssetId: "asset_11111111111111111111111111111111"
    };
    const response = await POST(
      new NextRequest("http://localhost/api/generate/photo/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/photo/start",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("keeps the selected image engine when proxying photo start", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ jobId: "job_photo_gpt2" }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("../photo/start/route");

    const payload = {
      userInput: "사진으로 고품질 메뉴 광고",
      sourceAssetId: "asset_11111111111111111111111111111111",
      imageGenerationEngine: "gpt_image_2",
      requestedEngine: "gpt_image_2",
      t2iEngine: "gpt_image_2"
    };
    const response = await POST(
      new NextRequest("http://localhost/api/generate/photo/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      })
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator/api/v1/marketing/photo/start",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });
});
