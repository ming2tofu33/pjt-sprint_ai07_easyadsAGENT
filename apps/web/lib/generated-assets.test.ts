import { describe, expect, it } from "vitest";
import { buildGeneratedAssetUrl, normalizeGeneratedOutputPath } from "./generated-assets";

describe("generated asset URLs", () => {
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
});
