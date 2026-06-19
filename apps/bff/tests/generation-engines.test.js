import { describe, expect, it, vi } from "vitest";

import { buildApp } from "../src/app.js";
import { imageGenerationEngines, normalizeImageGenerationEngine } from "../src/contracts/generation-engines.js";


function jsonResponse(payload) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" }
  });
}


describe("generation engine contract", () => {
  it("exposes only the canonical public engine set", () => {
    expect(imageGenerationEngines).toEqual(["gpt_image_2", "flux2_klein_4b", "sd35_large"]);
    expect(imageGenerationEngines).not.toContain("gpt_image_1");
  });

  it("normalizes legacy aliases only through the compatibility helper", () => {
    expect(normalizeImageGenerationEngine("gpt_image_1")).toBe("gpt_image_2");
    expect(normalizeImageGenerationEngine("flux_schnell")).toBe("flux2_klein_4b");
    expect(normalizeImageGenerationEngine("unknown")).toBeUndefined();
    expect(normalizeImageGenerationEngine("gpt_image_1", { allowLegacyAlias: false })).toBeUndefined();
  });

  it.each(imageGenerationEngines)("accepts canonical public engine %s", async (engine) => {
    const fetchImpl = vi.fn(async () => jsonResponse({ jobId: "photo_engine" }));
    const app = buildApp({ orchestratorBaseUrl: "http://orchestrator", fetchImpl });

    const response = await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "Create an ad",
        sourceAssetId: "asset_11111111111111111111111111111111",
        imageGenerationEngine: engine,
        requestedEngine: engine,
        t2iEngine: engine
      }
    });

    expect(response.statusCode).toBe(200);
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      imageGenerationEngine: engine,
      requestedEngine: engine,
      t2iEngine: engine
    });
    await app.close();
  });

  it.each(["gpt_image_1", "unknown"])("rejects non-public engine %s", async (engine) => {
    const fetchImpl = vi.fn();
    const app = buildApp({ fetchImpl });
    const response = await app.inject({
      method: "POST",
      url: "/api/generate/photo/start",
      payload: {
        userInput: "Create an ad",
        sourceAssetId: "asset_11111111111111111111111111111111",
        imageGenerationEngine: engine
      }
    });

    expect(response.statusCode).toBe(400);
    expect(fetchImpl).not.toHaveBeenCalled();
    await app.close();
  });
});
