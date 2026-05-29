import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams()
}));

vi.mock("@/lib/api-client", () => ({
  startChatGeneration: vi.fn(async () => ({
    jobId: "job_1",
    threadId: "thread_1",
    status: "generating_copy_candidates",
    context: {
      businessType: "카페",
      itemOrService: "딸기라떼",
      promotionGoal: "신메뉴 출시"
    },
    copyCandidates: [
      { id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" },
      { id: "copy_2", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" }
    ],
    recommendedCopyId: "copy_1"
  })),
  createChatBrief: vi.fn(async () => ({
    jobId: "job_1",
    threadId: "thread_1",
    status: "done",
    brief: {
      purpose: "신메뉴 출시",
      item: "딸기라떼",
      copy: "봄을 닮은 한 잔, 딸기라떼 출시",
      tone: "상큼한 카페 무드",
      channel: "인스타 스토리 (9:16)",
      imageDirection: "크림톤 배경"
    }
  }))
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    replace: navigationMock.replace
  }),
  useSearchParams: () => navigationMock.searchParams
}));

describe("ChatGenerateClient", () => {
  beforeEach(() => {
    navigationMock.push.mockClear();
    navigationMock.replace.mockClear();
    navigationMock.searchParams = new URLSearchParams();
  });

  it("walks through the four chat generation steps", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    expect(screen.getByText("레퍼런스 보고 만들기")).toBeTruthy();
    fireEvent.click(screen.getByText("대화로 시작하기"));
    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("문구와 채널을 골라주세요")).toBeTruthy();
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("인스타 스토리 (9:16)")).toBeTruthy();

    fireEvent.click(screen.getByText(/찰떡 광고 생성하기/));
    expect(screen.getByText("광고 생성 중")).toBeTruthy();
    expect(screen.getByText("찰떡 광고를 만들고 있어요")).toBeTruthy();

    fireEvent.click(screen.getByText("기다리는 동안 둘러보기"));
    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();
    expect(screen.getByText(/광고 생성 중 ·/)).toBeTruthy();
  });

  it("keeps similar style browsing open after generation completes", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    fireEvent.click(screen.getByText("문구 고르기"));
    fireEvent.click(screen.getByText("브리프 확인하기"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    vi.useFakeTimers();
    fireEvent.click(screen.getByText(/찰떡 광고 생성하기/));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000);
    });

    expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy();
    fireEvent.click(screen.getByText("비슷한 스타일 더 보기"));
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();
    expect(screen.queryByText("찰떡 광고 시안이 완성됐어요")).toBeNull();
    vi.useRealTimers();
  });

  it("opens the reference gallery from the home mock hub", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("레퍼런스 보고 만들기"));
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();
    expect(screen.getByText("찰떡 레퍼런스 둘러보기")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("홈으로"));
    expect(screen.getByText("레퍼런스 보고 만들기")).toBeTruthy();
  });

  it("opens the studio entry and dashboard tabs from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /보관함/ }));
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /마이페이지/ }));
    expect(screen.getByText("추천 & 브랜드 키트")).toBeTruthy();
  });

  it("renders dashboard surfaces from query params", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    navigationMock.searchParams = new URLSearchParams("surface=studio");
    const { rerender } = render(<ChatGenerateClient />);
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    navigationMock.searchParams = new URLSearchParams("surface=reference");
    rerender(<ChatGenerateClient />);
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();

    navigationMock.searchParams = new URLSearchParams("surface=ads");
    rerender(<ChatGenerateClient />);
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    navigationMock.searchParams = new URLSearchParams("surface=brand");
    rerender(<ChatGenerateClient />);
    expect(screen.getByText("추천 & 브랜드 키트")).toBeTruthy();
  });

  it("pushes stable URLs when top-level tabs are selected", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat?surface=studio");

    fireEvent.click(screen.getAllByRole("button", { name: /레퍼런스/ }).at(-1)!);
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat?surface=reference");
  });

  it("shows realistic creative labels in reference cards", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    navigationMock.searchParams = new URLSearchParams("surface=reference");
    render(<ChatGenerateClient />);

    expect(screen.getByText("SPRING SALE")).toBeTruthy();
    expect(screen.getByText("SUMMER SALE")).toBeTruthy();
  });
});
