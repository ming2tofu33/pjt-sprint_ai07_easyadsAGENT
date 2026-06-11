import { describe, expect, it } from "vitest";
import {
  buildDashboardHref,
  parseDashboardStage,
  parseDashboardSurface
} from "./dashboard-navigation";

describe("dashboard navigation", () => {
  it("builds service-style dashboard hrefs", () => {
    expect(buildDashboardHref("home")).toBe("/");
    expect(buildDashboardHref("studio")).toBe("/studio");
    expect(buildDashboardHref("reference")).toBe("/reference");
    expect(buildDashboardHref("ads")).toBe("/ads");
    expect(buildDashboardHref("my")).toBe("/my");
    expect(buildDashboardHref("brand")).toBe("/brand/kit");
    expect(buildDashboardHref("photo")).toBe("/generate/photo");
    expect(buildDashboardHref("chat")).toBe("/generate/chat");
  });

  it("builds clean chat stage hrefs", () => {
    expect(buildDashboardHref("chat", "start")).toBe("/generate/chat");
    expect(buildDashboardHref("chat", "brief")).toBe("/generate/chat");
    expect(buildDashboardHref("chat", "generating")).toBe("/generate/chat/generating");
    expect(buildDashboardHref("chat", "complete")).toBe("/generate/chat/complete");
    expect(buildDashboardHref("chat", "similar")).toBe("/generate/chat/similar");
  });

  it("parses supported dashboard surfaces", () => {
    expect(parseDashboardSurface("home")).toBe("home");
    expect(parseDashboardSurface("studio")).toBe("studio");
    expect(parseDashboardSurface("reference")).toBe("reference");
    expect(parseDashboardSurface("ads")).toBe("ads");
    expect(parseDashboardSurface("my")).toBe("my");
    expect(parseDashboardSurface("brand")).toBe("brand");
    expect(parseDashboardSurface("chat")).toBe("chat");
    expect(parseDashboardSurface("photo")).toBe("photo");
  });

  it("falls back to home for missing or invalid dashboard surfaces", () => {
    expect(parseDashboardSurface(undefined)).toBe("home");
    expect(parseDashboardSurface(null)).toBe("home");
    expect(parseDashboardSurface("settings")).toBe("home");
    expect(parseDashboardSurface("")).toBe("home");
  });

  it("parses supported dashboard stages", () => {
    expect(parseDashboardStage("start")).toBe("start");
    expect(parseDashboardStage("brief")).toBe("brief");
    expect(parseDashboardStage("generating")).toBe("generating");
    expect(parseDashboardStage("complete")).toBe("complete");
    expect(parseDashboardStage("similar")).toBe("similar");
  });

  it("falls back to start for missing or invalid dashboard stages", () => {
    expect(parseDashboardStage(undefined)).toBe("start");
    expect(parseDashboardStage(null)).toBe("start");
    expect(parseDashboardStage("review")).toBe("start");
    expect(parseDashboardStage("")).toBe("start");
  });
});
