import { afterEach, describe, expect, it, vi } from "vitest";

describe("supabase session helper", () => {
  afterEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.doUnmock("./browser");
  });

  it("throws when anonymous Supabase session creation is unavailable", async () => {
    vi.doMock("./browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: null } })
        }
      })
    }));
    const { getSupabaseAccessToken } = await import("./session");

    await expect(getSupabaseAccessToken()).rejects.toThrow(
      "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요."
    );
  });

  it("throws when anonymous Supabase session creation yields no result", async () => {
    const signInAnonymously = vi.fn(async () => undefined);
    vi.doMock("./browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: null } }),
          signInAnonymously
        }
      })
    }));
    const { getSupabaseAccessToken } = await import("./session");

    await expect(getSupabaseAccessToken()).rejects.toThrow(
      "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요."
    );
    expect(signInAnonymously).toHaveBeenCalledTimes(1);
  });

  it("throws when anonymous Supabase session creation returns an auth error", async () => {
    vi.doMock("./browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: null } }),
          signInAnonymously: async () => ({
            data: { session: null },
            error: new Error("auth failed")
          })
        }
      })
    }));
    const { getSupabaseAccessToken } = await import("./session");

    await expect(getSupabaseAccessToken()).rejects.toThrow(
      "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요."
    );
  });

  it("throws when anonymous Supabase session creation yields no token", async () => {
    vi.doMock("./browser", () => ({
      createSupabaseBrowserClient: () => ({
        auth: {
          getSession: async () => ({ data: { session: null } }),
          signInAnonymously: async () => ({
            data: { session: { access_token: "   " } },
            error: null
          })
        }
      })
    }));
    const { getSupabaseAccessToken } = await import("./session");

    await expect(getSupabaseAccessToken()).rejects.toThrow(
      "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요."
    );
  });
});
