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
      copyFallbackUsed: false,
      copyFallbackReason: null,
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
      copyFallbackUsed: false,
      copyFallbackReason: null,
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

    fireEvent.click(screen.getByRole("button", { name: "직접 문구 입력 선택" }));
    fireEvent.change(screen.getByLabelText("생성 재개 메인 문구 입력"), {
      target: { value: "내가 쓴 딸기라떼 문구" },
    });
    fireEvent.change(screen.getByLabelText("생성 재개 보조 문구 입력"), {
      target: { value: "오늘 오후 한정" },
    });
    fireEvent.click(screen.getByRole("button", { name: "선택 완료" }));

    expect(onSubmitCustomCopy).toHaveBeenCalledWith({
      userCustomHeadline: "내가 쓴 딸기라떼 문구",
      userCustomSubcopy: "오늘 오후 한정",
      label: "내가 쓴 딸기라떼 문구 / 오늘 오후 한정",
    });
  });

  it("requires an explicit 선택 완료 click and does not pre-select the recommendation", () => {
    const onSelectCopyCandidate = vi.fn();
    const interrupt: ParsedGenerationJobInterrupt = {
      type: "copy_candidate_selection",
      candidates: [
        { id: "copy_1", headline: "추천 문구", subcopy: null, cta: "확인하기" },
        { id: "copy_2", headline: "두 번째 문구", subcopy: null, cta: "확인하기" },
      ],
      recommendedCandidateId: "copy_1",
      copyCandidateOrigin: "rule_based",
      copyFallbackUsed: false,
      copyFallbackReason: null,
      raw: { type: "copy_candidate_selection" },
    };

    render(
      <GenerationJobInterruptStep
        interrupt={interrupt}
        onBack={vi.fn()}
        onSelectCopyCandidate={onSelectCopyCandidate}
        onSubmitCustomCopy={vi.fn()}
      />
    );

    // Nothing pre-selected: 선택 완료 disabled, no card aria-pressed.
    const submit = screen.getByRole("button", { name: "선택 완료" });
    expect(submit).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: /추천 문구 선택/ })).toHaveProperty("ariaPressed", "false");

    // Clicking a card selects locally but does not submit.
    fireEvent.click(screen.getByRole("button", { name: /두 번째 문구 선택/ }));
    expect(onSelectCopyCandidate).not.toHaveBeenCalled();
    expect(submit).toHaveProperty("disabled", false);

    // Only 선택 완료 submits the chosen candidate.
    fireEvent.click(submit);
    expect(onSelectCopyCandidate).toHaveBeenCalledWith({ selectedCopyId: "copy_2", label: "두 번째 문구" });
  });

  it("shows fallback provenance for deferred copy candidate selection", () => {
    const interrupt: ParsedGenerationJobInterrupt = {
      type: "copy_candidate_selection",
      candidates: [{ id: "copy_1", headline: "Fallback copy", subcopy: null, cta: null }],
      recommendedCandidateId: "copy_1",
      copyCandidateOrigin: "fallback",
      copyFallbackUsed: true,
      copyFallbackReason: "api_call_disabled",
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

    expect(screen.getByText(/임시 추천 문구/)).toBeTruthy();
    expect(screen.getByText("AI 문구 생성이 완료되지 않아 기본 추천 문구를 표시했습니다.")).toBeTruthy();
    expect(screen.queryByText(/AI 추천 문구/)).toBeNull();
  });

  it("renders validated compliance suggestions before legacy suggested text", () => {
    const interrupt: ParsedGenerationJobInterrupt = {
      type: "copy_compliance_review",
      status: "evidence_required",
      summary: "광고 문구에 확인이 필요한 표현이 있어요.",
      actions: [{ id: "use_suggestion", label: "안전한 문구로 수정", available: true }],
      findings: [
        {
          finding_id: "finding_1",
          field: "headline",
          matched_text: "최고",
          severity: "evidence_required",
          reason: "객관적 근거가 필요한 최상급 표현입니다.",
          suggested_text: "고객 만족 코칭 프로그램",
          suggestions: [
            {
              id: "suggestion_1",
              text: "정성껏 준비한 고기 한 접시",
              validation_status: "pass",
              rationale: "재검수를 통과했어요.",
            },
          ],
        },
      ],
      raw: { type: "copy_compliance_review" },
    };

    render(
      <GenerationJobInterruptStep
        interrupt={interrupt}
        onBack={vi.fn()}
        onSelectCopyCandidate={vi.fn()}
        onSubmitCustomCopy={vi.fn()}
        onComplianceAction={vi.fn()}
      />
    );

    expect(screen.getByText("정성껏 준비한 고기 한 접시")).toBeTruthy();
    expect(screen.queryByText("고객 만족 코칭 프로그램")).toBeNull();
  });
});
