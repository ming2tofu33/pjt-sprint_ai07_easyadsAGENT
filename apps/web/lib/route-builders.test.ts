import { describe, expect, it } from "vitest";
import { buildAdHref } from "./ad-navigation";
import { buildBrandKitHref } from "./brand-kit-navigation";
import { buildExceptionStateHref } from "./exception-state-navigation";
import { buildMyHref } from "./my-navigation";
import { buildNotificationHref } from "./notification-navigation";
import { buildOnboardingHref } from "./onboarding-navigation";
import { buildReferenceStyleHref } from "./reference-navigation";

describe("route builders", () => {
  it("builds ad save flow hrefs", () => {
    expect(buildAdHref("result-1")).toBe("/ads/result-1");
    expect(buildAdHref("result-1", "save")).toBe("/ads/result-1/save");
    expect(buildAdHref("result-1", "saved")).toBe("/ads/result-1/saved");
  });

  it("builds brand kit flow hrefs", () => {
    expect(buildBrandKitHref()).toBe("/brand/kit");
    expect(buildBrandKitHref("start")).toBe("/brand/kit");
    expect(buildBrandKitHref("info")).toBe("/brand/kit/info");
    expect(buildBrandKitHref("tone")).toBe("/brand/kit/tone");
    expect(buildBrandKitHref("complete")).toBe("/brand/kit/complete");
  });

  it("builds exception state hrefs", () => {
    expect(buildExceptionStateHref("searchEmpty")).toBe("/reference/empty");
    expect(buildExceptionStateHref("archiveEmpty")).toBe("/ads/empty");
    expect(buildExceptionStateHref("uploadFailed")).toBe("/generate/photo/upload-failed");
    expect(buildExceptionStateHref("generationFailed")).toBe("/generate/chat/failed");
  });

  it("builds my page hrefs", () => {
    expect(buildMyHref()).toBe("/my");
    expect(buildMyHref("home")).toBe("/my");
    expect(buildMyHref("account")).toBe("/my/account");
    expect(buildMyHref("usage")).toBe("/my/usage");
    expect(buildMyHref("settings")).toBe("/settings");
  });

  it("builds notification hrefs", () => {
    expect(buildNotificationHref()).toBe("/notifications");
    expect(buildNotificationHref("center")).toBe("/notifications");
    expect(buildNotificationHref("complete")).toBe("/notifications/complete");
    expect(buildNotificationHref("failed")).toBe("/notifications/failed");
    expect(buildNotificationHref("settings")).toBe("/notifications/settings");
  });

  it("builds onboarding hrefs", () => {
    expect(buildOnboardingHref()).toBe("/onboarding");
    expect(buildOnboardingHref("intro")).toBe("/onboarding");
    expect(buildOnboardingHref("modes")).toBe("/onboarding");
    expect(buildOnboardingHref("brief")).toBe("/onboarding");
    expect(buildOnboardingHref("start")).toBe("/onboarding");
  });

  it("builds reference style flow hrefs", () => {
    expect(buildReferenceStyleHref("ref-strawberry-poster")).toBe("/reference/ref-strawberry-poster");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "analysis")).toBe("/reference/ref-strawberry-poster/analysis");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "similar")).toBe("/reference/ref-strawberry-poster/similar");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "start")).toBe("/reference/ref-strawberry-poster/start");
  });
});
