import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  prefetch: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    prefetch: navigationMock.prefetch
  })
}));

describe("OnboardingFlowStep", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    window.localStorage.clear();
    navigationMock.push.mockClear();
    navigationMock.prefetch.mockClear();
  });

  it("completes onboarding when a start mode is selected", async () => {
    const { OnboardingFlowStep } = await import("./OnboardingFlowStep");

    render(<OnboardingFlowStep />);

    fireEvent.click(screen.getByRole("button", { name: /다음/ }));
    fireEvent.click(screen.getByRole("button", { name: /대화로 시작하기/ }));

    expect(window.localStorage.getItem(ONBOARDING_COMPLETED_STORAGE_KEY)).toBe(ONBOARDING_COMPLETED_VALUE);
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
  });
});
