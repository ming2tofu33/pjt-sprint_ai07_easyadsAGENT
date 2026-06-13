import { afterEach, describe, expect, it, vi } from "vitest";
import { buildGeneratedAssetUrl, normalizeGeneratedOutputPath } from "./generated-assets";

describe("generated asset URLs", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("maps backend output paths to the web asset route", () => {
    expect(buildGeneratedAssetUrl("data/outputs/job_1/final_composite.png")).toBe(
      "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
    );
  });

  it("extracts generated output paths from absolute backend paths", () => {
    expect(normalizeGeneratedOutputPath("/workspace/easyads/data/outputs/job_1/mock_0.png")).toBe(
      "data/outputs/job_1/mock_0.png"
    );
  });

  it("rejects paths outside generated outputs", () => {
    expect(buildGeneratedAssetUrl("data/uploads/input.png")).toBeNull();
    expect(buildGeneratedAssetUrl("data/outputs/../secrets.env")).toBeNull();
  });

  it("does not build local output URLs in production unless explicitly enabled", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_LOCAL_GENERATED_ASSETS", "");

    expect(buildGeneratedAssetUrl("data/outputs/job_1/final_composite.png")).toBeNull();

    vi.stubEnv("NEXT_PUBLIC_ENABLE_LOCAL_GENERATED_ASSETS", "true");

    expect(buildGeneratedAssetUrl("data/outputs/job_1/final_composite.png")).toBe(
      "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
    );
  });
});
