import { beforeEach, describe, expect, it } from "vitest";
import {
  BRAND_KIT_STORAGE_KEY,
  brandKitMeta,
  brandKitProducts,
  readBrandKitDraft,
  readSavedBrandKit,
  saveBrandKit,
  writeBrandKitDraft
} from "./brand-kit-storage";

describe("brand-kit-storage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("returns an empty draft before a brand kit is saved", () => {
    const draft = readBrandKitDraft();

    expect(draft.status).toBe("draft");
    expect(draft.businessName).toBe("");
    expect(readSavedBrandKit()).toBeNull();
  });

  it("keeps draft data separate from saved brand kits", () => {
    writeBrandKitDraft({
      businessName: "연남 테스트 카페",
      businessType: "카페",
      region: "연남동",
      sns: "@test_cafe",
      tones: ["따뜻한"],
      colors: ["#FFD7C9"],
      phrases: ["예약은 DM 주세요"],
      products: ["라떼"]
    });

    expect(readBrandKitDraft().businessName).toBe("연남 테스트 카페");
    expect(readSavedBrandKit()).toBeNull();
  });

  it("saves and formats a completed brand kit", () => {
    const saved = saveBrandKit({
      businessName: "연남 테스트 카페",
      businessType: "카페",
      region: "연남동",
      sns: "@test_cafe",
      tones: ["따뜻한", "깔끔한"],
      colors: ["#FFD7C9"],
      phrases: ["예약은 DM 주세요"],
      products: ["라떼", "케이크"]
    });

    expect(saved.status).toBe("saved");
    expect(readSavedBrandKit()?.businessName).toBe("연남 테스트 카페");
    expect(brandKitMeta(saved)).toBe("카페 · 연남동 · @test_cafe");
    expect(brandKitProducts(saved)).toBe("라떼, 케이크");
    expect(window.sessionStorage.getItem(BRAND_KIT_STORAGE_KEY)).toContain("연남 테스트 카페");
  });
});
