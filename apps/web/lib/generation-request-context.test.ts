import { beforeEach, describe, expect, it } from "vitest";
import { saveBrandKit } from "./brand-kit-storage";
import {
  GENERATION_DRAFT_PROMPT_STORAGE_KEY,
  appendSavedBrandKitContext,
  buildBrandKitGenerationContext,
  readGenerationDraftPrompt,
  writeGenerationDraftPrompt
} from "./generation-request-context";

describe("generation-request-context", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("keeps prompts unchanged when no brand kit is saved", () => {
    expect(appendSavedBrandKitContext("광고 만들어줘")).toBe("광고 만들어줘");
  });

  it("appends saved brand kit details for generation requests", () => {
    const brandKit = saveBrandKit({
      businessName: "연남 테스트 카페",
      businessType: "카페",
      region: "연남동",
      sns: "@test_cafe",
      tones: ["따뜻한"],
      colors: ["#FFD7C9"],
      phrases: ["예약은 DM 주세요"],
      products: ["대표 메뉴"]
    });

    expect(buildBrandKitGenerationContext(brandKit)).toContain("가게 이름: 연남 테스트 카페");
    expect(appendSavedBrandKitContext("신메뉴 광고 만들어줘")).toContain("[브랜드 키트]");
    expect(appendSavedBrandKitContext("신메뉴 광고 만들어줘")).toContain("대표 상품/서비스: 대표 메뉴");
  });

  it("uses a one-time draft prompt for cross-route starts", () => {
    writeGenerationDraftPrompt("레퍼런스 스타일로 광고 만들어줘");

    expect(window.sessionStorage.getItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY)).toBe("레퍼런스 스타일로 광고 만들어줘");
    expect(readGenerationDraftPrompt()).toBe("레퍼런스 스타일로 광고 만들어줘");
    expect(readGenerationDraftPrompt()).toBe("");
  });
});
