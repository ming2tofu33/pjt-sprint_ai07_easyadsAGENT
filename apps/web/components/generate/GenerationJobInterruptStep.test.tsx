import React from "react";
import { render, screen } from "@testing-library/react";
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
});
