import { describe, expect, it } from "vitest";
import { buildNotificationHref } from "./notification-navigation";

describe("notification navigation", () => {
  it("builds clean notification hrefs", () => {
    expect(buildNotificationHref()).toBe("/notifications");
    expect(buildNotificationHref("center")).toBe("/notifications");
    expect(buildNotificationHref("complete")).toBe("/notifications/complete");
    expect(buildNotificationHref("failed")).toBe("/notifications/failed");
    expect(buildNotificationHref("settings")).toBe("/notifications/settings");
  });
});
