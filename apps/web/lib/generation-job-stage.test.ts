import { describe, expect, it } from "vitest";
import type { GenerationJob } from "@/lib/api-client";
import { generationStageViewFromJob, generationStatusSteps } from "./generation-job-stage";

function job(status: string, currentStage?: string): GenerationJob {
  return {
    job_id: "job_1",
    status,
    progress: currentStage
      ? {
          progress_percent: 50,
          current_stage: currentStage
        }
      : undefined
  };
}

describe("generation job stage view", () => {
  it("uses queued copy before the backend job starts running", () => {
    expect(generationStageViewFromJob(job("queued")).label).toBe("생성 요청 접수 중");
    expect(generationStageViewFromJob(job("queued")).activeStepIndex).toBe(0);
  });

  it("maps planning stages to the brief preparation step", () => {
    const view = generationStageViewFromJob(job("running", "planning"));

    expect(view.label).toBe("광고 방향 정리 중");
    expect(view.activeStepIndex).toBe(1);
  });

  it("maps modal and image stages to image generation without using percent values", () => {
    const view = generationStageViewFromJob(job("running", "modal_running"));

    expect(view.label).toBe("이미지 생성 중");
    expect(view.activeStepIndex).toBe(2);
  });

  it("exposes backend progress percent and message when available", () => {
    const view = generationStageViewFromJob({
      job_id: "job_progress",
      status: "running",
      progress: {
        progress_percent: 72,
        current_stage: "modal_running",
        message: "FLUX 모델이 이미지를 만들고 있어요."
      }
    });

    expect(view.progressPercent).toBe(72);
    expect(view.detail).toBe("FLUX 모델이 이미지를 만들고 있어요.");
  });

  it("marks completed jobs as terminal storage-ready work", () => {
    const view = generationStageViewFromJob(job("done", "completed"));

    expect(view.label).toBe("보관함 연결 완료");
    expect(view.activeStepIndex).toBe(3);
    expect(view.isTerminal).toBe(true);
  });

  it("keeps failed jobs terminal without showing progress completion", () => {
    const view = generationStageViewFromJob(job("failed", "failed"));

    expect(view.label).toBe("생성 오류 확인 중");
    expect(view.isFailed).toBe(true);
  });

  it("exposes the visible stage labels in display order", () => {
    expect(generationStatusSteps).toEqual(["생성 요청 접수", "광고 방향 정리", "이미지 생성", "보관함 연결 확인"]);
  });
});
