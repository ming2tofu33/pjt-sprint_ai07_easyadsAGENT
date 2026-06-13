import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("chat thread Next routes", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("lists threads with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "user_1", is_anonymous: false }))
      .mockResolvedValueOnce(jsonResponse({ threads: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const response = await GET(
      new NextRequest("http://localhost/api/chat-threads?limit=10", {
        headers: { authorization: "Bearer token_1" }
      })
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://orchestrator/api/v1/chat-threads?limit=10&userId=user_1&accountType=user"
    );
  });

  it("reads a thread with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "guest_1", is_anonymous: true }))
      .mockResolvedValueOnce(jsonResponse({ thread: { threadId: "thread_1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./[threadId]/route");

    const response = await GET(
      new NextRequest("http://localhost/api/chat-threads/thread_1", {
        headers: { authorization: "Bearer guest_token_1" }
      }),
      { params: { threadId: "thread_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://orchestrator/api/v1/chat-threads/thread_1?userId=guest_1&accountType=guest"
    );
  });

  it("reads thread messages with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "user_1" }))
      .mockResolvedValueOnce(jsonResponse({ messages: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./[threadId]/messages/route");

    const response = await GET(
      new NextRequest("http://localhost/api/chat-threads/thread_1/messages?limit=20", {
        headers: { authorization: "Bearer token_1" }
      }),
      { params: { threadId: "thread_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://orchestrator/api/v1/chat-threads/thread_1/messages?limit=20&userId=user_1&accountType=user"
    );
  });

  it("reads thread state with verified user query params", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "user_1" }))
      .mockResolvedValueOnce(jsonResponse({ state: {} }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./[threadId]/state/route");

    const response = await GET(
      new NextRequest("http://localhost/api/chat-threads/thread_1/state", {
        headers: { authorization: "Bearer token_1" }
      }),
      { params: { threadId: "thread_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://orchestrator/api/v1/chat-threads/thread_1/state?userId=user_1&accountType=user"
    );
  });

  it("archives a thread through the orchestrator", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ thread: { threadId: "thread_1" } })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./[threadId]/archive/route");

    const response = await POST(
      new NextRequest("http://localhost/api/chat-threads/thread_1/archive", { method: "POST" }),
      { params: { threadId: "thread_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://orchestrator/api/v1/chat-threads/thread_1/archive");
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: "POST" }));
  });
});
