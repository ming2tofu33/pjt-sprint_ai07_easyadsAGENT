import { describe, expect, it } from "vitest";
import { getSafeAdminRedirectPath, isAdminRole } from "./admin-auth";

describe("isAdminRole", () => {
  it.each(["owner", "admin", "editor"])("accepts %s", (role) => {
    expect(isAdminRole(role)).toBe(true);
  });

  it.each([null, undefined, "", "user", "OWNER"])("rejects %s", (role) => {
    expect(isAdminRole(role)).toBe(false);
  });
});

describe("getSafeAdminRedirectPath", () => {
  it("keeps internal admin paths", () => {
    expect(getSafeAdminRedirectPath("/admin/references")).toBe("/admin/references");
  });

  it("falls back for external URLs", () => {
    expect(getSafeAdminRedirectPath("https://evil.example/admin")).toBe("/admin");
  });

  it("falls back for non-admin internal paths", () => {
    expect(getSafeAdminRedirectPath("/studio")).toBe("/admin");
  });

  it("falls back for protocol-relative paths", () => {
    expect(getSafeAdminRedirectPath("//evil.example/admin")).toBe("/admin");
  });
});
