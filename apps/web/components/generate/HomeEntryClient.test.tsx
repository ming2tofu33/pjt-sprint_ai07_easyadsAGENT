import React from "react";
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";

const navigationMock = vi.hoisted(() => ({
  replace: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: navigationMock.replace
  })
}));

vi.mock("@/app/generate/chat/ChatGenerateClient", () => ({
  ChatGenerateClient: ({ initialSurface }: { initialSurface: string }) => <div>dashboard:{initialSurface}</div>
}));

describe("HomeEntryClient", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    window.localStorage.clear();
    navigationMock.replace.mockClear();
  });

  it("shows a mobile loading state before redirecting first-time visitors", async () => {
    const { HomeEntryClient } = await import("./HomeEntryClient");

    render(<HomeEntryClient />);

    expect(screen.getByRole("status")).toHaveTextContent("개떡찰떡을 준비하고 있어요");
    expect(screen.getByRole("status")).toHaveTextContent("처음 방문하셨다면 사용법을 안내해 드릴게요.");
    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith("/onboarding"));
  });

  it("renders the home dashboard when onboarding is completed", async () => {
    window.localStorage.setItem(ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE);
    const { HomeEntryClient } = await import("./HomeEntryClient");

    render(<HomeEntryClient />);

    await waitFor(() => expect(screen.getByText("dashboard:home")).toBeTruthy());
    expect(navigationMock.replace).not.toHaveBeenCalled();
  });
});
