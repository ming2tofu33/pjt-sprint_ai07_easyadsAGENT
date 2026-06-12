import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./ChatGeneratePage", () => ({
  ChatGeneratePage: ({ initialSurface }: { initialSurface: string }) => <div>surface:{initialSurface}</div>
}));

describe("AdsSurfacePage", () => {
  it("renders the archive surface outside the route module", async () => {
    const { AdsSurfacePage } = await import("./AdsSurfacePage");

    render(<AdsSurfacePage />);

    expect(screen.getByText("surface:ads")).toBeTruthy();
  });
});
