import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createInitialChatFlowState } from "@/lib/chat-flow";
import type { ChatFlowState } from "@/types/marketing";
import { BriefConfirmStep } from "./BriefConfirmStep";

(globalThis as typeof globalThis & { React: typeof React }).React = React;

describe("BriefConfirmStep", () => {
  it("renders the selected banner channel instead of the default feed label", () => {
    const state: ChatFlowState = {
      ...createInitialChatFlowState(),
      step: 4,
      selectedChannelId: "banner",
      inferredContext: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_banner", headline: "배너 문구" }],
      selectedCopyId: "copy_banner"
    };

    render(
      <BriefConfirmStep
        state={state}
        onBack={vi.fn()}
        onGenerate={vi.fn()}
        onRefineBrief={vi.fn()}
      />
    );

    expect(screen.getByText("배너 (16:9)")).toBeTruthy();
    expect(screen.queryByText("인스타 피드 (1:1)")).toBeNull();
  });
});
