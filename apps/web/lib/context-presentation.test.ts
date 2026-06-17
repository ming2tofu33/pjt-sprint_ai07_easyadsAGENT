import { describe, expect, it } from "vitest";
import { campaignIntentLabel, contextBusinessSummary, contextItemLabel, contextItemSummary, contextPurposeSummary, displayContextValue } from "./context-presentation";

describe("context-presentation", () => {
  it("maps canonical campaign launch tokens to display labels", () => {
    expect(campaignIntentLabel("store_opening")).toBe("\uc2e0\uaddc \uc624\ud508 \ud64d\ubcf4");
    expect(campaignIntentLabel("new_product_launch")).toBe("\uc2e0\uc0c1\ud488 \ucd9c\uc2dc");
    expect(campaignIntentLabel("new_menu_launch")).toBe("\uc2e0\uba54\ub274 \ucd9c\uc2dc");
    expect(campaignIntentLabel("service_launch")).toBe("\uc2e0\uaddc \uc11c\ube44\uc2a4 \uc2dc\uc791");
    expect(campaignIntentLabel("grand_opening")).toBeTruthy();
  });

  it("prefers promotion goal but falls back to campaign intent", () => {
    expect(
      contextPurposeSummary({
        businessType: null,
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: "\ud504\ub9ac\ubbf8\uc5c4 \ubdf0\ud2f0\uc0f5",
        advertisedSubjectType: "business",
        campaignIntent: "store_opening",
      }),
    ).toBe("\uc2e0\uaddc \uc624\ud508 \ud64d\ubcf4");
    expect(displayContextValue("new_product_launch")).toBe("\uc2e0\uc0c1\ud488 \ucd9c\uc2dc");
  });

  it("covers the required canonical intent tokens in frontend presentation mapping", () => {
    for (const token of ["store_opening", "new_product_launch", "new_menu_launch", "service_launch"] as const) {
      expect(campaignIntentLabel(token)).toBeTruthy();
    }
  });

  it("maps raw business semantics to display labels only at presentation time", () => {
    expect(contextBusinessSummary({ businessType: "beauty_salon" })).toBe("\ubdf0\ud2f0/\ubbf8\uc6a9");
    expect(contextBusinessSummary({ businessType: "restaurant" })).toBe("\uc74c\uc2dd\uc810/\uc2dd\ub2f9");
  });

  it("returns null for unknown campaign intent tokens — no raw token exposure", () => {
    expect(campaignIntentLabel("unknown_internal_token")).toBeNull();
    expect(campaignIntentLabel("service_reopening")).toBeNull();
    expect(campaignIntentLabel("seasonal_reactivation")).toBeNull();
    expect(campaignIntentLabel("")).toBeNull();
    expect(campaignIntentLabel(null)).toBeNull();
    expect(campaignIntentLabel(undefined)).toBeNull();
  });

  it("displayContextValue does not fall back to campaign intent for unknown tokens", () => {
    expect(displayContextValue("unknown_internal_token")).toBeUndefined();
    expect(displayContextValue("service_reopening")).toBeUndefined();
  });

  it("contextPurposeSummary returns null for unknown campaign intent", () => {
    expect(
      contextPurposeSummary({
        businessType: null,
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: null,
        advertisedSubjectType: null,
        campaignIntent: "unknown_internal_token",
      })
    ).toBeNull();
  });

  it("contextItemLabel returns 상품/서비스 when itemOrService is present", () => {
    expect(
      contextItemLabel({
        businessType: null,
        itemOrService: "\ub527\uae30\ub77c\ub5bc",
        promotionGoal: null,
        advertisedSubject: null,
        advertisedSubjectType: null,
        campaignIntent: null,
      })
    ).toBe("\uc0c1\ud488/\uc11c\ube44\uc2a4");
  });

  it("contextItemLabel returns 광고 대상 when only advertisedSubject is present", () => {
    expect(
      contextItemLabel({
        businessType: null,
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: "\ud504\ub9ac\ubbf8\uc5c4 \ubdf0\ud2f0\uc0f5",
        advertisedSubjectType: "business",
        campaignIntent: null,
      })
    ).toBe("\uad11\uace0 \ub300\uc0c1");
  });

  it("contextItemLabel returns 상품/서비스 when both are absent", () => {
    expect(
      contextItemLabel({
        businessType: "beauty_salon",
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: null,
        advertisedSubjectType: null,
        campaignIntent: null,
      })
    ).toBe("\uc0c1\ud488/\uc11c\ube44\uc2a4");
  });

  it("contextItemLabel prefers itemOrService over advertisedSubject", () => {
    expect(
      contextItemLabel({
        businessType: null,
        itemOrService: "\ub77c\ub5bc",
        promotionGoal: null,
        advertisedSubject: "\uc0f5",
        advertisedSubjectType: "business",
        campaignIntent: null,
      })
    ).toBe("\uc0c1\ud488/\uc11c\ube44\uc2a4");
  });

  it("contextItemSummary falls back to advertisedSubject when itemOrService is absent", () => {
    expect(
      contextItemSummary({
        businessType: null,
        itemOrService: null,
        promotionGoal: null,
        advertisedSubject: "\ud504\ub9ac\ubbf8\uc5c4 \ubdf0\ud2f0\uc0f5",
        advertisedSubjectType: "business",
        campaignIntent: null,
      })
    ).toBe("\ud504\ub9ac\ubbf8\uc5c4 \ubdf0\ud2f0\uc0f5");
  });
});
