import { describe, expect, it } from "vitest";
import { normalizeSelectedChannelId, toCanonicalAdFormat } from "./ad-formats";

describe("ad-formats", () => {
  it("normalizes known ad formats and canonical channel ids", () => {
    expect(normalizeSelectedChannelId("banner")).toBe("banner");
    expect(normalizeSelectedChannelId("instagram_story")).toBe("instagram-story");
    expect(toCanonicalAdFormat("instagram-story")).toBe("instagram_story");
  });

  it("rejects unknown channel-like values instead of coercing them", () => {
    expect(normalizeSelectedChannelId("unknown_format")).toBeNull();
    expect(toCanonicalAdFormat("unknown-format")).toBeUndefined();
  });
});
