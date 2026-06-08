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
  it("does not render a generated image for local-only artifacts", () => {
    renderStep();

    expect(screen.getByText("이미지 저장 연결을 확인해야 해요")).toBeTruthy();
    expect(screen.getByText("이미지는 만들어졌지만 보관함에서 열 수 있는 주소를 아직 확인하지 못했어요.")).toBeTruthy();
    expect(screen.queryByRole("img", { name: /생성|광고|시안/i })).toBeNull();
    expect(screen.getByRole("button", { name: /보관함 연결 대기 중/ }).hasAttribute("disabled")).toBe(true);
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
