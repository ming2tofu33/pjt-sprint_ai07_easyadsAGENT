import { describe, expect, it } from "vitest";
import { buildBrandKitHref } from "./brand-kit-navigation";

describe("brand kit navigation", () => {
  it("builds clean brand kit flow hrefs", () => {
    expect(buildBrandKitHref()).toBe("/brand/kit");
    expect(buildBrandKitHref("start")).toBe("/brand/kit");
    expect(buildBrandKitHref("info")).toBe("/brand/kit/info");
    expect(buildBrandKitHref("tone")).toBe("/brand/kit/tone");
    expect(buildBrandKitHref("complete")).toBe("/brand/kit/complete");
  });
});
