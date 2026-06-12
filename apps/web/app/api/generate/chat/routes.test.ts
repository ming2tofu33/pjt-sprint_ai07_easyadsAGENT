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

  it("proxies chat start to the legacy marketing chat endpoint", async () => {
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
      "http://orchestrator/v1/marketing/chat/start",
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

  it("proxies chat brief selections to the legacy marketing brief endpoint", async () => {
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
      "http://orchestrator/v1/marketing/chat/brief",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("proxies chat answers to the legacy marketing answer endpoint", async () => {
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
      "http://orchestrator/v1/marketing/chat/answer",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });

  it("proxies photo start to the legacy marketing photo endpoint", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async () => jsonResponse({ jobId: "job_photo_1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("../photo/start/route");

    const payload = {
      userInput: "사진으로 메뉴 광고",
      sourceImagePath: "data/uploads/photo_1.png"
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
      "http://orchestrator/v1/marketing/photo/start",
      expect.objectContaining({ method: "POST", body: JSON.stringify(payload) })
    );
  });
});
