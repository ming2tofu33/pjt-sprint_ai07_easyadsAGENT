import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push
  })
}));

describe("NotificationCenterStep", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    navigationMock.push.mockClear();
  });

  it("filters sample notifications by status chips", async () => {
    const { NotificationCenterStep } = await import("./NotificationCenterStep");

    render(<NotificationCenterStep />);

    fireEvent.click(screen.getByRole("button", { name: "샘플 알림 보기" }));
    expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy();
    expect(screen.getByText("광고 생성 중이에요")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "생성 완료" }));

    expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy();
    expect(screen.queryByText("광고 생성 중이에요")).toBeNull();
    expect(screen.queryByText("광고 생성에 실패했어요")).toBeNull();
  });

  it("routes every sample notification action to a dummy destination", async () => {
    const { NotificationCenterStep } = await import("./NotificationCenterStep");

    render(<NotificationCenterStep />);

    fireEvent.click(screen.getByRole("button", { name: "샘플 알림 보기" }));

    fireEvent.click(screen.getByRole("button", { name: "진행 상황 보기" }));
    expect(navigationMock.push).toHaveBeenLastCalledWith("/generate/chat/generating");

    fireEvent.click(screen.getByRole("button", { name: "브랜드 키트 보기" }));
    expect(navigationMock.push).toHaveBeenLastCalledWith("/brand/kit/complete");

    fireEvent.click(screen.getByRole("button", { name: "결과 확인하기" }));
    expect(navigationMock.push).toHaveBeenLastCalledWith("/notifications/complete");

    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(navigationMock.push).toHaveBeenLastCalledWith("/notifications/failed");
  });

  it("marks sample notifications as read with the header action", async () => {
    const { NotificationCenterStep } = await import("./NotificationCenterStep");

    const { container } = render(<NotificationCenterStep />);

    fireEvent.click(screen.getByRole("button", { name: "샘플 알림 보기" }));
    expect(container.querySelectorAll("[class*='notificationUnread']").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "모두 읽음" }));
    expect(container.querySelectorAll("[class*='notificationUnread']")).toHaveLength(0);
  });
});
