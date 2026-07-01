import { describe, expect, it } from "vitest";

import { generationJobSchema, photoStartSchema } from "./generate";

describe("asset id generation contracts", () => {
  it("accepts public asset ids for photo and generation job requests", () => {
    expect(
      photoStartSchema.safeParse({
        userInput: "Create an ad",
        sourceAssetId: "asset_11111111111111111111111111111111",
        referenceAssetId: "asset_22222222222222222222222222222222"
      }).success
    ).toBe(true);
    expect(
      generationJobSchema.safeParse({
        userInput: "Create an ad",
        sourceAssetId: "asset_11111111111111111111111111111111",
        referenceAssetId: "asset_22222222222222222222222222222222"
      }).success
    ).toBe(true);
  });

  it("rejects legacy local image paths", () => {
    expect(photoStartSchema.safeParse({ userInput: "Create an ad", sourceImagePath: "legacy/source.png" }).success).toBe(false);
    expect(generationJobSchema.safeParse({ userInput: "Create an ad", referenceImagePath: "legacy/reference.png" }).success).toBe(false);
  });

  it("accepts only canonical public image engines", () => {
    expect(
      generationJobSchema.safeParse({
        userInput: "Create an ad",
        imageGenerationEngine: "gpt_image_2",
        requestedEngine: "flux2_klein_4b",
        t2iEngine: "sd35_large"
      }).success
    ).toBe(true);
    expect(generationJobSchema.safeParse({ userInput: "Create an ad", imageGenerationEngine: "gpt_image_1" }).success).toBe(false);
    expect(generationJobSchema.safeParse({ userInput: "Create an ad", t2iEngine: "unknown" }).success).toBe(false);
  });
});
