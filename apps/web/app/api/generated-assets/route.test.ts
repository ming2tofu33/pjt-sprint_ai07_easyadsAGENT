import { readFile, stat } from "node:fs/promises";
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

const fsMocks = vi.hoisted(() => ({
  readFile: vi.fn(async () => Buffer.from([1, 2, 3])),
  stat: vi.fn(async () => ({
    isFile: () => true
  }))
}));

vi.mock("node:fs/promises", () => ({
  default: {
    readFile: fsMocks.readFile,
    stat: fsMocks.stat
  },
  readFile: fsMocks.readFile,
  stat: fsMocks.stat
}));

describe("generated assets route", () => {
  it("allows immutable browser caching for generated output files", async () => {
    const { GET } = await import("./route");

    const response = await GET(
      new NextRequest("http://localhost/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png")
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("public, max-age=31536000, immutable");
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(stat).toHaveBeenCalled();
    expect(readFile).toHaveBeenCalled();
  });
});
