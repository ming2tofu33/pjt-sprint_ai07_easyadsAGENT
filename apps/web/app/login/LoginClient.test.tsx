import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginClient } from "./LoginClient";

const authMock = {
  getUser: vi.fn(),
  linkIdentity: vi.fn(),
  signInWithOAuth: vi.fn()
};

vi.mock("@/lib/supabase/browser", () => ({
  createSupabaseBrowserClient: () => ({ auth: authMock })
}));

describe("LoginClient", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    authMock.getUser.mockReset();
    authMock.linkIdentity.mockReset();
    authMock.signInWithOAuth.mockReset();
  });

  it("links Google identity when the current Supabase user is anonymous", async () => {
    authMock.getUser.mockResolvedValue({
      data: { user: { id: "guest_uuid_1", is_anonymous: true } }
    });
    authMock.linkIdentity.mockResolvedValue({ data: {}, error: null });
    authMock.signInWithOAuth.mockResolvedValue({ data: {}, error: null });

    render(<LoginClient nextPath="/generate/chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Google 계정으로 로그인" }));

    await waitFor(() => expect(authMock.linkIdentity).toHaveBeenCalled());
    expect(authMock.signInWithOAuth).not.toHaveBeenCalled();
    expect(authMock.linkIdentity).toHaveBeenCalledWith({
      provider: "google",
      options: {
        redirectTo: "http://localhost:3000/auth/callback?next=%2Fgenerate%2Fchat",
        queryParams: {
          access_type: "offline",
          prompt: "consent"
        }
      }
    });
  });

  it("starts normal Google OAuth when there is no current user", async () => {
    authMock.getUser.mockResolvedValue({ data: { user: null } });
    authMock.signInWithOAuth.mockResolvedValue({ data: {}, error: null });
    authMock.linkIdentity.mockResolvedValue({ data: {}, error: null });

    render(<LoginClient nextPath="/generate/chat" />);
    fireEvent.click(screen.getByRole("button", { name: "Google 계정으로 로그인" }));

    await waitFor(() => expect(authMock.signInWithOAuth).toHaveBeenCalled());
    expect(authMock.linkIdentity).not.toHaveBeenCalled();
  });
});
