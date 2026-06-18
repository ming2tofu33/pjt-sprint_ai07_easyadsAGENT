import { describe, expect, it } from "vitest";
import type { GenerationJob } from "./api-client";
import {
  getGenerationJobPollingDecision,
  MAX_CONSECUTIVE_POLL_ERRORS,
  withPollingJitter
} from "./generation-job-polling";

function job(status: string, stage = status): GenerationJob {
  return { job_id: "job_1", status, progress: { progress_percent: 0, current_stage: stage } };
}

describe("generation job polling policy", () => {
  it.each(["done", "failed", "cancelled"])("stops for terminal status %s", (status) => {
    expect(getGenerationJobPollingDecision({ job: job(status), attempt: 0, consecutiveErrors: 0, documentHidden: false }).shouldContinue).toBe(false);
  });

  it("stops for waiting user input", () => {
    expect(getGenerationJobPollingDecision({ job: job("waiting_user_input"), attempt: 0, consecutiveErrors: 0, documentHidden: false }).reason).toBe("waiting_user_input");
  });

  it("slows generating and hidden-document polling", () => {
    const early = getGenerationJobPollingDecision({ job: job("running", "planning"), attempt: 1, consecutiveErrors: 0, documentHidden: false });
    const generating = getGenerationJobPollingDecision({ job: job("running", "generating_image"), attempt: 5, consecutiveErrors: 0, documentHidden: false });
    const hidden = getGenerationJobPollingDecision({ job: job("running"), attempt: 1, consecutiveErrors: 0, documentHidden: true });
    expect(generating.delayMs).toBeGreaterThan(early.delayMs);
    expect(hidden.delayMs).toBeGreaterThan(generating.delayMs);
  });

  it("backs off network errors and stops at the limit", () => {
    const retry = getGenerationJobPollingDecision({ job: job("running"), attempt: 1, consecutiveErrors: 3, documentHidden: false });
    const stopped = getGenerationJobPollingDecision({ job: job("running"), attempt: 1, consecutiveErrors: MAX_CONSECUTIVE_POLL_ERRORS, documentHidden: false });
    expect(retry).toMatchObject({ shouldContinue: true, delayMs: 4000, reason: "network_backoff" });
    expect(stopped).toMatchObject({ shouldContinue: false, reason: "network_error_limit" });
  });

  it("supports deterministic bounded jitter", () => {
    expect(withPollingJitter(1000, () => 0)).toBe(900);
    expect(withPollingJitter(1000, () => 1)).toBe(1100);
    expect(withPollingJitter(20000, () => 1)).toBe(15000);
  });
});
