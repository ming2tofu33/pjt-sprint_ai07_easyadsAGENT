import { describe, expect, it } from "vitest";
import { buildAdHref } from "./ad-navigation";

describe("ad navigation", () => {
  it("builds clean ad save flow hrefs", () => {
    expect(buildAdHref("result-1")).toBe("/ads/result-1");
    expect(buildAdHref("result-1", "save")).toBe("/ads/result-1/save");
    expect(buildAdHref("result-1", "saved")).toBe("/ads/result-1/saved");
  });
});
