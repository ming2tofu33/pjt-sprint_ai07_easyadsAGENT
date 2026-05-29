import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

describe("ChatGenerateClient", () => {
  it("walks through the four chat generation steps", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

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
});
