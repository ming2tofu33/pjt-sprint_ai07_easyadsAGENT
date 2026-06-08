import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createInitialChatFlowState } from "@/lib/chat-flow";
import type { ChatFlowState } from "@/types/marketing";
import { GenerationCompleteStep } from "./GenerationCompleteStep";

(globalThis as typeof globalThis & { React: typeof React }).React = React;

function renderStep(overrides: Partial<ChatFlowState> = {}) {
  const state: ChatFlowState = {
    ...createInitialChatFlowState(),
    step: 4,
    generationJob: {
      job_id: "job_local",
      status: "done",
      result_payload: {
        final_image_url: null,
        download_url: null,
        final_image_path: "data/outputs/job_local/final_0.png"
      }
    },
    ...overrides
  };
  const onOpenArchive = vi.fn();

  render(
    <GenerationCompleteStep
      state={state}
      onBrowseSimilar={vi.fn()}
      onGoHome={vi.fn()}
      onRegenerate={vi.fn()}
      onOpenArchive={onOpenArchive}
    />
  );

  return { onOpenArchive };
}

describe("GenerationCompleteStep", () => {
  it("shows a friendly pending state when a request exists but no job is attached yet", () => {
    const { onOpenArchive } = renderStep({
      userInput: "우리 카페 신메뉴 광고 만들어줘",
      generationJob: null,
      inferredContext: {
        businessType: "카페",
        itemOrService: "신메뉴",
        promotionGoal: "신메뉴 출시"
      }
    });

    expect(screen.getByText("이미지를 만들고 있어요")).toBeTruthy();
    expect(screen.getByText("완성되면 보관함에 자동으로 저장돼요. 잠시만 기다려주세요.")).toBeTruthy();
    expect(screen.getByText("미리보기는 완성 후 표시돼요")).toBeTruthy();
    expect(screen.getByText("이미지가 준비되면 이 영역이 결과 카드로 바뀝니다.")).toBeTruthy();
    expect(screen.queryByText("완료 전에는 깨진 이미지나 임시 카드를 보여주지 않아요.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /보관함에서 기다리기/ }));
    expect(onOpenArchive).toHaveBeenCalledTimes(1);
  });

  it("does not render a generated image for local-only artifacts", () => {
    const { onOpenArchive } = renderStep();

    expect(screen.getByText("이미지 저장 연결을 확인해야 해요")).toBeTruthy();
    expect(screen.getByText("이미지는 만들어졌지만 보관함에서 열 수 있는 주소를 아직 확인하지 못했어요.")).toBeTruthy();
    expect(screen.queryByRole("img", { name: /생성|광고|시안/i })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /보관함에서 확인하기/ }));
    expect(onOpenArchive).toHaveBeenCalledTimes(1);
  });

  it("opens archive from the primary CTA when a browser image URL is available", () => {
    const { onOpenArchive } = renderStep({
      generationJob: {
        job_id: "job_url",
        status: "done",
        result_payload: {
          final_image_url: "https://cdn.example.com/generated/job_url/final_0.png",
          download_url: "https://cdn.example.com/generated/job_url/final_0.png",
          final_image_path: "data/outputs/job_url/final_0.png"
        }
      }
    });

    fireEvent.click(screen.getByRole("button", { name: /보관함에서 확인하기/ }));

    expect(onOpenArchive).toHaveBeenCalledTimes(1);
  });
});
