import { describe, expect, it } from "vitest";
import { buildOnboardingHref } from "./onboarding-navigation";

describe("onboarding navigation", () => {
  it("builds clean onboarding hrefs", () => {
    expect(buildOnboardingHref()).toBe("/onboarding");
    expect(buildOnboardingHref("intro")).toBe("/onboarding");
    expect(buildOnboardingHref("modes")).toBe("/onboarding");
    expect(buildOnboardingHref("brief")).toBe("/onboarding");
    expect(buildOnboardingHref("start")).toBe("/onboarding");
  });
});
