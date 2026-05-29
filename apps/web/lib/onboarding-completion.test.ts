import { describe, expect, it } from "vitest";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "./onboarding-completion";

describe("onboarding completion constants", () => {
  it("uses a stable localStorage key and value", () => {
    expect(ONBOARDING_COMPLETED_STORAGE_KEY).toBe("easyads_onboarding_completed");
    expect(ONBOARDING_COMPLETED_VALUE).toBe("true");
  });
});
