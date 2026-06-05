import { describe, expect, it, vi } from "vitest";
import { deleteCurrentAccount, getAccountDeleteErrorMessage } from "./account-delete";

describe("getAccountDeleteErrorMessage", () => {
  it("maps missing service role configuration to a user-facing message", () => {
    expect(getAccountDeleteErrorMessage("account_delete_not_configured")).toContain("계정 삭제 설정");
  });

  it("maps missing sessions to a re-login message", () => {
    expect(getAccountDeleteErrorMessage("not_authenticated")).toContain("다시 로그인");
  });

  it("uses fallback messages for unknown errors", () => {
    expect(getAccountDeleteErrorMessage("unknown", "서버 오류")).toBe("서버 오류");
  });
});

describe("deleteCurrentAccount", () => {
  it("sends a DELETE request to the account deletion route", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ success: true }), { status: 200 }));

    await expect(deleteCurrentAccount(fetchImpl as unknown as typeof fetch)).resolves.toEqual({ success: true });
    expect(fetchImpl).toHaveBeenCalledWith("/api/account/delete", {
      method: "DELETE",
      headers: { accept: "application/json" }
    });
  });

  it("returns a friendly failure result from API error payloads", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ success: false, error_code: "account_delete_not_configured" }), {
          status: 503
        })
    );

    await expect(deleteCurrentAccount(fetchImpl as unknown as typeof fetch)).resolves.toMatchObject({
      success: false,
      errorCode: "account_delete_not_configured",
      message: expect.stringContaining("계정 삭제 설정")
    });
  });
});
