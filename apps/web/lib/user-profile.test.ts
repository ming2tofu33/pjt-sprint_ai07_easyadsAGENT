import { describe, expect, it } from "vitest";
import { buildAppUserProfile, getDisplayNameFromUser, getLoginMethodFromUser } from "./user-profile";

describe("getDisplayNameFromUser", () => {
  it("prefers Google full name", () => {
    expect(getDisplayNameFromUser({ email: "owner@example.com", user_metadata: { full_name: "홍길동" } })).toBe("홍길동");
  });

  it("falls back to email name", () => {
    expect(getDisplayNameFromUser({ email: "owner@example.com", user_metadata: {} })).toBe("owner");
  });
});

describe("getLoginMethodFromUser", () => {
  it("formats Google provider", () => {
    expect(getLoginMethodFromUser({ app_metadata: { provider: "google" }, identities: [] })).toBe("Google 계정");
  });

  it("does not expose non-Google provider labels", () => {
    expect(getLoginMethodFromUser({ app_metadata: { provider: "email" }, identities: [] })).toBe("Google 계정 확인 필요");
  });

  it("falls back to Google wording when provider is only present in identities", () => {
    expect(getLoginMethodFromUser({ app_metadata: {}, identities: [{ provider: "google" } as never] })).toBe("Google 계정");
  });
});

describe("buildAppUserProfile", () => {
  it("returns null for guests", () => {
    expect(buildAppUserProfile(null)).toBeNull();
  });

  it("returns null for Supabase anonymous users", () => {
    expect(
      buildAppUserProfile({
        id: "guest_uuid_1",
        email: "",
        user_metadata: {},
        app_metadata: {},
        identities: [],
        is_anonymous: true
      } as never)
    ).toBeNull();
  });
});
