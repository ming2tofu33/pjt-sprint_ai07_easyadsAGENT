import { describe, expect, it } from "vitest";
import {
  getPendingGenerationJobOptionQuestion,
  hasPendingGenerationJobInterrupt,
  parseGenerationJobInterrupt
} from "./generation-job-interrupt";
import type { GenerationJob } from "./api-client";

describe("generation job interrupt helpers", () => {
  it("extracts option questions from generation job metadata", () => {
    const job: GenerationJob = {
      job_id: "job_1",
      status: "waiting_user_input",
      progress: { progress_percent: 50, current_stage: "waiting_user_input" },
      metadata: {
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "business_type",
            question: "어떤 업종인가요?",
            options: [{ id: 1, label: "카페", value: "cafe" }]
          }
        }
      }
    };

    expect(hasPendingGenerationJobInterrupt(job)).toBe(true);
    expect(getPendingGenerationJobOptionQuestion(job)?.field).toBe("business_type");
  });

  it("returns null for unsupported interrupts", () => {
    const job: GenerationJob = {
      job_id: "job_1",
      status: "waiting_user_input",
      metadata: { pending_interrupt: { type: "copy_candidate_selection" } }
    };

    expect(hasPendingGenerationJobInterrupt(job)).toBe(true);
    expect(getPendingGenerationJobOptionQuestion(job)).toBeNull();
  });

  it("parses copy candidate selection interrupts", () => {
    expect(
      parseGenerationJobInterrupt({
        type: "copy_candidate_selection",
        candidates: [
          {
            id: "copy_1",
            headline: "오늘만 할인",
            metadata: { compliance: { status: "evidence_required", finding_count: 1, disabled: true } }
          },
          { id: "copy_2", headline: "이번 주 신메뉴" }
        ],
        recommended_candidate_id: "copy_1",
        copy_candidate_origin: "rule_based"
      })
    ).toMatchObject({
      type: "copy_candidate_selection",
      recommendedCandidateId: "copy_1",
      copyCandidateOrigin: "rule_based",
      copyFallbackUsed: false,
      copyFallbackReason: null,
      candidates: [
        {
          id: "copy_1",
          headline: "오늘만 할인",
          metadata: { compliance: { status: "evidence_required", finding_count: 1, disabled: true } }
        },
        { id: "copy_2", headline: "이번 주 신메뉴" }
      ]
    });

    expect(
      parseGenerationJobInterrupt({
        type: "copy_candidate_selection",
        candidates: [{ id: "copy_1", headline: "오늘만 할인" }],
        metadata: { copyCandidateOrigin: "fallback" }
      })
    ).toMatchObject({
      type: "copy_candidate_selection",
      copyCandidateOrigin: "fallback",
      copyFallbackUsed: true
    });
  });

  it("parses copy fallback provenance from interrupt metadata", () => {
    expect(
      parseGenerationJobInterrupt({
        type: "copy_candidate_selection",
        candidates: [{ id: "copy_1", headline: "Fallback copy" }],
        metadata: {
          copyCandidateOrigin: "fallback",
          copyFallbackUsed: true,
          copyFallbackReason: "api_call_disabled"
        }
      })
    ).toMatchObject({
      type: "copy_candidate_selection",
      copyCandidateOrigin: "fallback",
      copyFallbackUsed: true,
      copyFallbackReason: "api_call_disabled"
    });
  });

  it("parses custom copy input interrupts", () => {
    expect(
      parseGenerationJobInterrupt({
        type: "custom_copy_input",
        fields: [
          {
            field: "user_custom_headline",
            placeholder: "포스터 메인 카피를 입력해주세요",
            required: true,
            max_recommended_chars: 15
          },
          {
            field: "user_custom_subcopy",
            placeholder: "서브 카피 또는 이벤트 상세 내용을 입력해주세요",
            required: false
          }
        ]
      })
    ).toMatchObject({
      type: "custom_copy_input",
      fields: [
        {
          field: "user_custom_headline",
          label: "메인 문구",
          placeholder: "포스터 메인 카피를 입력해주세요",
          required: true,
          maxRecommendedChars: 15
        },
        {
          field: "user_custom_subcopy",
          label: "보조 문구",
          placeholder: "서브 카피 또는 이벤트 상세 내용을 입력해주세요",
          required: false
        }
      ]
    });
  });
});
