import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationEngineSelector } from "./GenerationEngineSelector";

describe("GenerationEngineSelector", () => {
  it("shows GPT-image-2, FLUX, and SD options without GPT-image-1", () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;

    render(<GenerationEngineSelector value="gpt_image_2" onChange={vi.fn()} />);

    expect(screen.getByText("GPT-image-2")).toBeTruthy();
    expect(screen.getByText("FLUX.2 Klein 4B")).toBeTruthy();
    expect(screen.getByText("SD3.5 Large")).toBeTruthy();
    expect(screen.queryByText("GPT-image-1")).toBeNull();
  });
});
