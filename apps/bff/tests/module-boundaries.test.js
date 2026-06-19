import { readFile } from "node:fs/promises";
import { describe, expect, it, vi } from "vitest";

import { buildApp, DEFAULT_BODY_LIMIT_BYTES } from "../src/app.js";
import { getBffConfig } from "../src/config.js";
import { proxyGetJson } from "../src/proxy/orchestrator.js";
import { generationJobSchema, photoStartSchema } from "../src/schemas/generation.js";

describe("BFF module boundaries", () => {
  it("keeps app.js focused on app construction and plugin registration", async () => {
    const source = await readFile(new URL("../src/app.js", import.meta.url), "utf8");
    expect(source).not.toContain("z.object");
    expect(source).not.toMatch(/app\.(get|post|patch|delete)\(/);
    expect(source.split(/\r?\n/).length).toBeLessThan(80);
  });

  it("registers the health plugin", async () => {
    const app = buildApp({ fetchImpl: vi.fn() });
    const response = await app.inject({ method: "GET", url: "/health" });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ status: "ok" });
    await app.close();
  });

  it("keeps asset ids and canonical engines in public generation schemas", () => {
    expect(photoStartSchema.safeParse({ userInput: "Create", sourceAssetId: "asset_1", imageGenerationEngine: "gpt_image_2" }).success).toBe(true);
    expect(photoStartSchema.safeParse({ userInput: "Create", sourceAssetId: "asset_1", sourceImagePath: "data/input.png" }).success).toBe(false);
    expect(generationJobSchema.safeParse({ userInput: "Create", referenceAssetId: "asset_2", imageGenerationEngine: "gpt_image_1" }).success).toBe(false);
  });

  it("preserves upstream status and error code through the proxy helper", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ error_code: "upstream_contract_error", detail: "invalid" }), {
      status: 422,
      headers: { "content-type": "application/json" }
    }));
    await expect(proxyGetJson({ fetchImpl, url: "http://orchestrator/api/v1/test" })).rejects.toMatchObject({
      statusCode: 422,
      errorCode: "upstream_contract_error"
    });
  });

  it("uses safe configuration defaults without exposing secrets", () => {
    const config = getBffConfig({}, {});
    expect(config.orchestratorBaseUrl).toBe("http://127.0.0.1:8000");
    expect(config.bodyLimitBytes).toBe(DEFAULT_BODY_LIMIT_BYTES);
    expect(config).not.toHaveProperty("internalSecret");
  });
});
