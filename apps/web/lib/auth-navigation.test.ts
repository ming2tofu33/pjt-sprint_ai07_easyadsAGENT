import { describe, expect, it } from "vitest";
import { buildLoginHref, getSafeAuthRedirectPath } from "./auth-navigation";

describe("getSafeAuthRedirectPath", () => {
  it.each(["/", "/my", "/my/account", "/studio", "/reference/ref-1", "/admin"])("allows %s", (path) => {
    expect(getSafeAuthRedirectPath(path)).toBe(path);
  });

  it("keeps query strings for allowed paths", () => {
    expect(getSafeAuthRedirectPath("/my?tab=profile")).toBe("/my?tab=profile");
  });

  it.each(["https://evil.example/my", "//evil.example/my", "javascript:alert(1)", "/api/references", "/_next/static"])("rejects %s", (path) => {
    expect(getSafeAuthRedirectPath(path)).toBe("/");
  });
});

describe("buildLoginHref", () => {
  it("encodes the next path", () => {
    expect(buildLoginHref("/my/account")).toBe("/login?next=%2Fmy%2Faccount");
  });

  it("falls back to app home for unsafe paths", () => {
    expect(buildLoginHref("https://evil.example")).toBe("/login?next=%2F");
  });
});
