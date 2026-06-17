import React from "react";
import "@testing-library/jest-dom/vitest";
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";

const copy: WaitingStatusCopy = {
  statusKey: "test_waiting",
  eyebrow: "테스트 상태",
  title: "작업을 확인하고 있어요",
  description: "사용자에게 지금 어떤 작업 중인지 알려줘요.",
  loop: ["첫 번째 작업 중이에요", "두 번째 작업 중이에요"]
};

afterEach(() => {
  vi.useRealTimers();
});

describe("WaitingStatusCard", () => {
  it("renders status copy with polite live updates", () => {
    render(<WaitingStatusCard copy={copy} />);

    expect(screen.getByText("테스트 상태")).toBeTruthy();
    expect(screen.getByText("작업을 확인하고 있어요")).toBeTruthy();
    expect(screen.getByText("사용자에게 지금 어떤 작업 중인지 알려줘요.")).toBeTruthy();
    expect(screen.getByText("첫 번째 작업 중이에요")).toBeTruthy();
    expect(screen.getByLabelText("작업 대기 상태")).toHaveAttribute("aria-live", "polite");
  });

  it("rotates the visible waiting message", () => {
    vi.useFakeTimers();
    render(<WaitingStatusCard copy={copy} intervalMs={1000} />);

    expect(screen.getByText("첫 번째 작업 중이에요")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("두 번째 작업 중이에요")).toBeTruthy();
  });
});
