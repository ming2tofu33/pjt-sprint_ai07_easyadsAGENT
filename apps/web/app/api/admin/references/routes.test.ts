import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("admin reference Next routes", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("requires a logged-in non-guest session before listing admin references", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("./route");

    const response = await GET(new NextRequest("http://localhost/api/admin/references"));
    const body = await response.json();

    expect(response.status).toBe(401);
    expect(body.error_code).toBe("admin_session_required");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates a reference template with verified user_id query param", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "admin_user_1" }))
      .mockResolvedValueOnce(jsonResponse({ template: { template_id: "ref_1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./route");

    const response = await POST(
      new NextRequest("http://localhost/api/admin/references", {
        method: "POST",
        headers: {
          authorization: "Bearer admin_token_1",
          "content-type": "application/json"
        },
        body: JSON.stringify({
          assetId: "asset_1",
          title: "카페 레퍼런스",
          category: "cafe"
        })
      })
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://orchestrator/api/v1/admin/references?user_id=admin_user_1");
  });

  it("publishes a reference template", async () => {
    vi.stubEnv("ORCHESTRATOR_BASE_URL", "http://orchestrator");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://supabase.local");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "admin_user_1" }))
      .mockResolvedValueOnce(jsonResponse({ template: { id: "ref_1", status: "published" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./[templateId]/publish/route");

    const response = await POST(
      new NextRequest("http://localhost/api/admin/references/ref_1/publish", {
        method: "POST",
        headers: { authorization: "Bearer admin_token_1" }
      }),
      { params: { templateId: "ref_1" } }
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://orchestrator/api/v1/admin/references/ref_1/publish");
  });
});
