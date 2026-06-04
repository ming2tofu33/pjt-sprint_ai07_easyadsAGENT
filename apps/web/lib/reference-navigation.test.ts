import { describe, expect, it } from "vitest";
import { buildReferenceStyleHref } from "./reference-navigation";

describe("reference navigation", () => {
  it("builds clean reference style flow hrefs", () => {
    expect(buildReferenceStyleHref("ref-strawberry-poster")).toBe("/reference/ref-strawberry-poster");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "analysis")).toBe("/reference/ref-strawberry-poster/analysis");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "similar")).toBe("/reference/ref-strawberry-poster/similar");
    expect(buildReferenceStyleHref("ref-strawberry-poster", "start")).toBe("/reference/ref-strawberry-poster/start");
  });
});
