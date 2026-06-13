import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("archive and upload Next routes", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("rejects generated archive creation without a public job id", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./items/route");

    const response = await POST(
      new NextRequest("http://localhost/api/archive/items", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "제목만 있음" })
      })
    );

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates generated archive items with verified user fields and snake_case payload", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "user_1" }))
      .mockResolvedValueOnce(jsonResponse({ item: { ad_id: "archive_1" } }, 201));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./items/route");

    const response = await POST(
      new NextRequest("http://localhost/api/archive/items", {
        method: "POST",
        headers: {
          authorization: "Bearer token_1",
          "content-type": "application/json"
        },
        body: JSON.stringify({
          title: "저장할 결과",
          publicJobId: "job_public_1",
          imageUrl: "https://spoofed.example.com/ignored.png",
          userId: "spoofed_user"
        })
      })
    );

    expect(response.status).toBe(201);
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://orchestrator/api/v1/archive/items");
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "저장할 결과",
          public_job_id: "job_public_1",
          image_url: "https://spoofed.example.com/ignored.png",
          status: "saved",
          source: "generated",
          user_id: "user_1",
          account_type: "user"
        })
      })
    );
  });

  it("lists archive items with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "guest_1", is_anonymous: true }))
      .mockResolvedValueOnce(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./items/route");

    const response = await GET(
      new NextRequest("http://localhost/api/archive/items?limit=20", {
        headers: { authorization: "Bearer guest_token_1" }
      })
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://orchestrator/api/v1/archive/items?limit=20&user_id=guest_1&account_type=guest"
    );
  });

  it("deletes archive items with DELETE", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ success: true })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { DELETE } = await import("./items/[archiveItemId]/route");

    const response = await DELETE(
      new NextRequest("http://localhost/api/archive/items/archive_1", { method: "DELETE" }),
      { params: { archiveItemId: "archive_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/archive/items/archive_1");
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "DELETE" }));
  });
});
