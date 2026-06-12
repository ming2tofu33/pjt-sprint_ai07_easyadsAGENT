import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationJobInterruptStep } from "./GenerationJobInterruptStep";
import type { ParsedGenerationJobInterrupt } from "@/lib/generation-job-interrupt";

(globalThis as typeof globalThis & { React: typeof React }).React = React;

describe("GenerationJobInterruptStep", () => {
  it("shows compliance badge and disables unsafe copy candidates", () => {
    const interrupt: ParsedGenerationJobInterrupt = {
      type: "copy_candidate_selection",
      candidates: [
        {
          id: "copy_1",
          headline: "국내 1위 카페",
          subcopy: null,
          cta: "확인하기",
          metadata: {
            compliance: {
              status: "evidence_required",
              finding_count: 1,
              disabled: true,
            },
          },
        },
      ],
      recommendedCandidateId: "copy_1",
      copyCandidateOrigin: "rule_based",
      raw: { type: "copy_candidate_selection" },
    };

    render(
      <GenerationJobInterruptStep
        interrupt={interrupt}
        onBack={vi.fn()}
        onSelectCopyCandidate={vi.fn()}
        onSubmitCustomCopy={vi.fn()}
      />
    );

    expect(screen.getByText("근거 필요")).toBeTruthy();
    expect(screen.getByText("규제 표현 1건")).toBeTruthy();
    expect(screen.getByRole("button", { name: /국내 1위 카페 선택/ })).toHaveProperty("disabled", true);
  });

  it("lets users enter custom copy from the candidate selection interrupt", () => {
    const onSubmitCustomCopy = vi.fn();
    const interrupt: ParsedGenerationJobInterrupt = {
      type: "copy_candidate_selection",
      candidates: [
        {
          id: "copy_1",
          headline: "오늘 저녁 딸기라떼 한 잔",
          subcopy: "달콤한 시즌 메뉴",
          cta: "확인하기",
        },
      ],
      recommendedCandidateId: "copy_1",
      copyCandidateOrigin: "rule_based",
      raw: { type: "copy_candidate_selection" },
    };

    render(
      <GenerationJobInterruptStep
        interrupt={interrupt}
        onBack={vi.fn()}
        onSelectCopyCandidate={vi.fn()}
        onSubmitCustomCopy={onSubmitCustomCopy}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "직접 문구 입력" }));
    fireEvent.change(screen.getByLabelText("생성 재개 메인 문구 입력"), {
      target: { value: "내가 쓴 딸기라떼 문구" },
    });
    fireEvent.change(screen.getByLabelText("생성 재개 보조 문구 입력"), {
      target: { value: "오늘 오후 한정" },
    });
    fireEvent.click(screen.getByRole("button", { name: "문구로 생성 이어가기" }));

    expect(onSubmitCustomCopy).toHaveBeenCalledWith({
      userCustomHeadline: "내가 쓴 딸기라떼 문구",
      userCustomSubcopy: "오늘 오후 한정",
      label: "내가 쓴 딸기라떼 문구 / 오늘 오후 한정",
    });
  });
});
