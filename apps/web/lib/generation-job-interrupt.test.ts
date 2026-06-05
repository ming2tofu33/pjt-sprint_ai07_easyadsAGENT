import { describe, expect, it } from "vitest";
import { getPendingGenerationJobOptionQuestion, hasPendingGenerationJobInterrupt } from "./generation-job-interrupt";
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
});
