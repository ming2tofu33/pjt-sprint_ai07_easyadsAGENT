import { describe, expect, it } from "vitest";
import { campaignIntentLabel, contextPurposeSummary, displayContextValue } from "./context-presentation";

describe("context-presentation", () => {
  it("maps canonical campaign launch tokens to display labels", () => {
    expect(campaignIntentLabel("store_opening")).toBe("신규 오픈 홍보");
    expect(campaignIntentLabel("new_product_launch")).toBe("신상품 출시");
    expect(campaignIntentLabel("new_menu_launch")).toBe("신메뉴 출시");
    expect(campaignIntentLabel("service_launch")).toBe("신규 서비스 시작");
    expect(campaignIntentLabel("grand_opening")).toBeTruthy();
  });

  it("prefers promotion goal but falls back to campaign intent", () => {
    expect(
      contextPurposeSummary({
        businessType: null,
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: "프리미엄 뷰티샵",
        advertisedSubjectType: "business",
        campaignIntent: "store_opening",
      }),
    ).toBe("신규 오픈 홍보");
    expect(displayContextValue("new_product_launch")).toBe("신상품 출시");
  });

  it("covers the required canonical intent tokens in frontend presentation mapping", () => {
    for (const token of ["store_opening", "new_product_launch", "new_menu_launch", "service_launch"] as const) {
      expect(campaignIntentLabel(token)).toBeTruthy();
    }
  });
});
