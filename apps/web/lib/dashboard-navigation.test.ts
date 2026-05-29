import { describe, expect, it } from "vitest";
import {
  buildDashboardHref,
  parseDashboardStage,
  parseDashboardSurface
} from "./dashboard-navigation";

describe("dashboard navigation", () => {
  it("builds dashboard hrefs with a surface query parameter", () => {
    expect(buildDashboardHref("home")).toBe("/generate/chat?surface=home");
    expect(buildDashboardHref("studio")).toBe("/generate/chat?surface=studio");
    expect(buildDashboardHref("reference")).toBe("/generate/chat?surface=reference");
    expect(buildDashboardHref("ads")).toBe("/generate/chat?surface=ads");
    expect(buildDashboardHref("brand")).toBe("/generate/chat?surface=brand");
    expect(buildDashboardHref("chat")).toBe("/generate/chat?surface=chat");
  });

  it("appends a stage query parameter when stage is provided", () => {
    expect(buildDashboardHref("studio", "start")).toBe("/generate/chat?surface=studio&stage=start");
    expect(buildDashboardHref("studio", "brief")).toBe("/generate/chat?surface=studio&stage=brief");
    expect(buildDashboardHref("studio", "generating")).toBe("/generate/chat?surface=studio&stage=generating");
    expect(buildDashboardHref("studio", "complete")).toBe("/generate/chat?surface=studio&stage=complete");
    expect(buildDashboardHref("studio", "similar")).toBe("/generate/chat?surface=studio&stage=similar");
  });

  it("parses supported dashboard surfaces", () => {
    expect(parseDashboardSurface("home")).toBe("home");
    expect(parseDashboardSurface("studio")).toBe("studio");
    expect(parseDashboardSurface("reference")).toBe("reference");
    expect(parseDashboardSurface("ads")).toBe("ads");
    expect(parseDashboardSurface("brand")).toBe("brand");
    expect(parseDashboardSurface("chat")).toBe("chat");
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
