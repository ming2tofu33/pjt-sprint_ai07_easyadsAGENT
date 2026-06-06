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

    expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy();
    expect(screen.getByText("완성된 이미지는 보관함에서 확인할 수 있어요.")).toBeTruthy();
    expect(screen.queryByRole("img", { name: /생성|광고|시안/i })).toBeNull();
  });

  it("opens archive from the primary CTA", () => {
    const { onOpenArchive } = renderStep();

    fireEvent.click(screen.getByRole("button", { name: /보관함에서 확인하기/ }));

    expect(onOpenArchive).toHaveBeenCalledTimes(1);
  });
});
