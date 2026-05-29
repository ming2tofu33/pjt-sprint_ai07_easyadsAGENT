import { describe, expect, it } from "vitest";
import { buildExceptionStateHref } from "./exception-state-navigation";

describe("exception state navigation", () => {
  it("builds direct mock routes for each exception state", () => {
    expect(buildExceptionStateHref("searchEmpty")).toBe("/reference/empty");
    expect(buildExceptionStateHref("archiveEmpty")).toBe("/ads/empty");
    expect(buildExceptionStateHref("uploadFailed")).toBe("/generate/photo/upload-failed");
    expect(buildExceptionStateHref("generationFailed")).toBe("/generate/chat/failed");
  });
});
