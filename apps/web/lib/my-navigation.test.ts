import { describe, expect, it } from "vitest";
import { buildMyHref } from "./my-navigation";

describe("my navigation", () => {
  it("builds clean my page hrefs", () => {
    expect(buildMyHref()).toBe("/my");
    expect(buildMyHref("home")).toBe("/my");
    expect(buildMyHref("account")).toBe("/my/account");
    expect(buildMyHref("usage")).toBe("/my/usage");
    expect(buildMyHref("settings")).toBe("/settings");
  });
});
