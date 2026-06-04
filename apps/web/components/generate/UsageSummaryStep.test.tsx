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

function seedGeneratedCreatives() {
  window.sessionStorage.setItem(
    "easyads_generated_creatives_v1",
    JSON.stringify([
      {
        id: "generated-1",
        title: "딸기라떼 광고",
        subtitle: "카페 · 인스타 피드",
        format: "1:1",
        imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        tone: "strawberry",
        badge: "실제 생성",
        status: "saved",
        channel: "인스타 피드",
        storage: "브라우저 임시 보관함",
        savedAt: "방금 생성",
        tags: ["카페"]
      },
      {
        id: "generated-2",
        title: "베이커리 포스터",
        subtitle: "베이커리 · 포스터",
        format: "4:5",
        imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_2%2Ffinal.png",
        tone: "cream",
        badge: "실제 생성",
        status: "saved",
        channel: "포스터",
        storage: "브라우저 임시 보관함",
        savedAt: "방금 생성",
        tags: ["베이커리"]
      },
      {
        id: "generated-3",
        title: "여름 음료 피드",
        subtitle: "카페 · 인스타 피드",
        format: "1:1",
        imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_3%2Ffinal.png",
        tone: "mint",
        badge: "실제 생성",
        status: "saved",
        channel: "인스타 피드",
        storage: "브라우저 임시 보관함",
        savedAt: "방금 생성",
        tags: ["음료"]
      },
      {
        id: "generated-4",
        title: "네 번째 생성 결과",
        subtitle: "리테일 · 스토리",
        format: "9:16",
        imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_4%2Ffinal.png",
        tone: "sunny",
        badge: "실제 생성",
        status: "saved",
        channel: "인스타 스토리",
        storage: "브라우저 임시 보관함",
        savedAt: "방금 생성",
        tags: ["리테일"]
      }
    ])
  );
}

describe("UsageSummaryStep", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    navigationMock.push.mockClear();
    navigationMock.back.mockClear();
    window.sessionStorage.clear();
  });

  it("opens period options and updates the selected period", async () => {
    const { UsageSummaryStep } = await import("./UsageSummaryStep");

    render(<UsageSummaryStep />);

    fireEvent.click(screen.getByRole("button", { name: "기간 선택" }));
    expect(screen.getByRole("button", { name: /지난 달/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /지난 달/ }));

    expect(screen.getByText("지난 달에 생성한 결과")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /최근 3개월/ })).toBeNull();
  });

  it("expands all usage history and opens usage details", async () => {
    seedGeneratedCreatives();
    const { UsageSummaryStep } = await import("./UsageSummaryStep");

    render(<UsageSummaryStep />);

    expect(screen.getByText("딸기라떼 광고")).toBeTruthy();
    expect(screen.queryByText("네 번째 생성 결과")).toBeNull();
    expect(screen.getByText("나머지 1개 내역은 전체 보기에서 확인할 수 있어요.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "전체 보기" }));
    expect(screen.getByText("네 번째 생성 결과")).toBeTruthy();
    expect(screen.getByRole("button", { name: "최근만 보기" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /사용량 더 보기/ }));
    expect(screen.getByRole("heading", { name: "사용량 안내" })).toBeTruthy();
    expect(screen.getByText("이미지 생성에 실패한 요청은 사용 내역에 포함하지 않습니다.")).toBeTruthy();
  });
});
