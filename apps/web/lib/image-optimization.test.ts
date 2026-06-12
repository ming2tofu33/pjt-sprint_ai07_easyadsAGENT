import { afterEach, describe, expect, it, vi } from "vitest";

describe("shouldUseNextImageOptimization", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("enables optimization for local and configured BFF reference images", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_BFF_BASE_URL", "http://127.0.0.1:4000");
    const { shouldUseNextImageOptimization } = await import("./image-optimization");

    expect(shouldUseNextImageOptimization("/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png")).toBe(true);
    expect(shouldUseNextImageOptimization("http://127.0.0.1:4000/api/references/temp-assets/group/ref.png")).toBe(true);
    expect(shouldUseNextImageOptimization("https://cdn.example.com/reference.png")).toBe(false);
    expect(shouldUseNextImageOptimization("//cdn.example.com/reference.png")).toBe(false);
    expect(shouldUseNextImageOptimization("data:image/png;base64,abc")).toBe(false);
    expect(shouldUseNextImageOptimization("Blob:http://127.0.0.1:4000/id")).toBe(false);
    expect(shouldUseNextImageOptimization(null)).toBe(false);
  });
});
