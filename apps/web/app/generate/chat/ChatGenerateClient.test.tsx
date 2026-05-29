import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn()
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
    back: navigationMock.back,
    replace: navigationMock.replace
  })
}));

describe("ChatGenerateClient", () => {
  beforeEach(() => {
    navigationMock.push.mockClear();
    navigationMock.back.mockClear();
    navigationMock.replace.mockClear();
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

  it("opens a reference style detail from the gallery", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    fireEvent.click(screen.getByRole("button", { name: "감성 카페 신메뉴 포스터 상세 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/reference/ref-strawberry-poster");
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
    expect(navigationMock.push).toHaveBeenCalledWith("/my");
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();
  });

  it("opens the photo flow from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /내 사진으로 만들기/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/generate/photo");
    expect(screen.getByText("사진으로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByText("사진 한 장으로 광고를 시작해보세요.")).toBeTruthy();
  });

  it("renders dashboard surfaces from route props", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="studio" />);
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="reference" />);
    expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="ads" />);
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="my" />);
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="brand" />);
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="photo" />);
    expect(screen.getByText("사진으로 찰떡 만들기")).toBeTruthy();
  });

  it("renders chat result stages from route props", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());
  });

  it("opens ad detail and save routes from generated results", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("찰떡 광고 시안이 완성됐어요")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "봄을 닮은 한 잔 상세 보기" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads/result-1");

    fireEvent.click(screen.getByText("선택한 시안 저장하기"));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads/result-1/save");
  });

  it("pushes stable URLs when top-level tabs are selected", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");

    fireEvent.click(screen.getAllByRole("button", { name: /레퍼런스/ }).at(-1)!);
    expect(navigationMock.push).toHaveBeenCalledWith("/reference");
  });

  it("offers previous and home escape routes from chat start", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));
    expect(navigationMock.back).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "홈으로" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/");
  });

  it("shows realistic creative labels in reference cards", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    expect(screen.getByText("SPRING SALE")).toBeTruthy();
    expect(screen.getByText("SUMMER SALE")).toBeTruthy();
  });

  it("shows feedback when a mock creative is saved", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    fireEvent.click(screen.getByLabelText("감성 카페 신메뉴 포스터 저장"));

    expect(screen.getByText("감성 카페 신메뉴 포스터를 보관함에 저장했어요.")).toBeTruthy();
  });

  it("shows feedback for recent ad and brand kit actions", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="ads" />);

    fireEvent.click(screen.getByRole("button", { name: "봄을 닮은 한 잔 다시 보기" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads/result-1");

    rerender(<ChatGenerateClient initialSurface="my" />);
    fireEvent.click(screen.getByRole("button", { name: /브랜드 키트 관리/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/brand/kit/info");
  });

  it("opens notifications from home and recent ads headers", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");

    rerender(<ChatGenerateClient initialSurface="ads" />);
    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");
  });

  it("walks through the photo generation mock flow", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    fireEvent.click(screen.getByRole("button", { name: "사진 분석 시작" }));
    expect(screen.getByText("AI 분석 결과")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "문구와 분위기 선택하기" }));
    expect(screen.getByText("추천 문구")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "브리프 확인하기" }));
    expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /찰떡 광고 생성하기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat/generating");
  });
});
