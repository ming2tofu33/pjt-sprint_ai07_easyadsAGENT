import { beforeEach, describe, expect, it } from "vitest";
import { saveBrandKit } from "./brand-kit-storage";
import {
  GENERATION_DRAFT_PROMPT_STORAGE_KEY,
  GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY,
  appendSavedBrandKitContext,
  buildBrandKitGenerationContext,
  clearGenerationDraftPrompt,
  clearGenerationRequestContext,
  readGenerationRequestContext,
  readGenerationDraftPrompt,
  readGenerationDraftReferenceTemplateId,
  saveGenerationRequestContext,
  writeGenerationDraftPrompt,
  writeGenerationDraftReferenceTemplateId
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
    expect(appendSavedBrandKitContext("신메뉴 광고 만들어줘")).toContain("[브랜드 파일]");
    expect(appendSavedBrandKitContext("신메뉴 광고 만들어줘")).toContain("대표 상품/서비스: 대표 메뉴");
  });

  it("keeps a cross-route draft prompt until the generation flow clears it", () => {
    writeGenerationDraftPrompt("샘플 스타일로 광고 만들어줘");

    expect(window.sessionStorage.getItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY)).toBe("샘플 스타일로 광고 만들어줘");
    expect(readGenerationDraftPrompt()).toBe("샘플 스타일로 광고 만들어줘");
    expect(readGenerationDraftPrompt()).toBe("샘플 스타일로 광고 만들어줘");

    clearGenerationDraftPrompt();

    expect(readGenerationDraftPrompt()).toBe("");
  });

  it("keeps a selected reference template until the generation flow clears it", () => {
    writeGenerationDraftReferenceTemplateId("temp_watermelon_juice_feed");

    expect(window.sessionStorage.getItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY)).toBe("temp_watermelon_juice_feed");
    expect(readGenerationDraftReferenceTemplateId()).toBe("temp_watermelon_juice_feed");
    expect(readGenerationDraftReferenceTemplateId()).toBe("temp_watermelon_juice_feed");

    clearGenerationDraftPrompt();

    expect(readGenerationDraftReferenceTemplateId()).toBe("");
  });

  it("keeps develop reference request context compatible with draft readers", () => {
    saveGenerationRequestContext({
      selectedReferenceTemplateId: "temp_watermelon_juice_feed",
      selectedReferenceTemplateTitle: "수박주스 블루 여름 피드",
      draftPrompt: "수박주스 블루 여름 피드 스타일로 광고를 만들고 싶어요.",
      source: "reference_gallery"
    });

    expect(readGenerationRequestContext()).toEqual({
      selectedReferenceTemplateId: "temp_watermelon_juice_feed",
      selectedReferenceTemplateTitle: "수박주스 블루 여름 피드",
      draftPrompt: "수박주스 블루 여름 피드 스타일로 광고를 만들고 싶어요.",
      source: "reference_gallery"
    });
    expect(readGenerationDraftPrompt()).toBe("수박주스 블루 여름 피드 스타일로 광고를 만들고 싶어요.");
    expect(readGenerationDraftReferenceTemplateId()).toBe("temp_watermelon_juice_feed");

    clearGenerationRequestContext();
    expect(readGenerationRequestContext()).toBeNull();
  });
});
