import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    back: navigationMock.back
  })
}));

describe("AppSettingsStep", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    navigationMock.push.mockClear();
    navigationMock.back.mockClear();
  });

  it("opens the onboarding guide from the help menu", async () => {
    const { AppSettingsStep } = await import("./AppSettingsStep");

    render(<AppSettingsStep />);

    expect(screen.getByRole("button", { name: /사용법 다시 보기/ })).toBeTruthy();
    expect(screen.queryByText("개떡찰떡 사용법")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /사용법 다시 보기/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/onboarding");
  });
});
