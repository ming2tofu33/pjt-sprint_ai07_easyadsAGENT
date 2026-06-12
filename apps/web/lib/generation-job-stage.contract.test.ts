import { describe, expect, it } from "vitest";

import type { GenerationJob } from "./api-client";
import { generationStageViewFromJob } from "./generation-job-stage";
import contract from "@/types/contracts/generation-stages.json";

function job(currentStage: string): GenerationJob {
  return {
    job_id: `job_${currentStage}`,
    status: currentStage === "failed" ? "failed" : currentStage === "completed" ? "done" : currentStage === "waiting_user_input" ? "waiting_user_input" : "running",
    progress: { progress_percent: 50, current_stage: currentStage },
    metadata: {}
  };
}

describe("generation stage FE/BE contract", () => {
  it.each(contract.stages)("renders a view for backend stage %s", (stage) => {
    const view = generationStageViewFromJob(job(stage));

    expect(view.label).toBeTruthy();
    expect(view.detail).toBeTruthy();
    expect(view.activeStepIndex).toBeGreaterThanOrEqual(0);
  });
});
