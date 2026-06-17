import { describe, expect, it } from "vitest";
import type { GenerationJob } from "./api-client";
import { resolveWaitingStatusCopy, waitingMessageAt } from "./generation-waiting-copy";

function job(status: string, currentStage?: string, metadata: Record<string, unknown> = {}): GenerationJob {
  return {
    job_id: `job_${status}_${currentStage ?? "none"}`,
    status,
    progress: currentStage ? { progress_percent: 50, current_stage: currentStage } : undefined,
    metadata
  };
}

describe("generation waiting copy", () => {
  it("rotates messages by index without throwing on empty lists", () => {
    expect(waitingMessageAt(["첫 번째", "두 번째"], 0)).toBe("첫 번째");
    expect(waitingMessageAt(["첫 번째", "두 번째"], 3)).toBe("두 번째");
    expect(waitingMessageAt([], 4)).toBe("");
  });

  it("uses photo upload copy before a generation job exists", () => {
    const copy = resolveWaitingStatusCopy({ context: "photo_upload" });

    expect(copy.title).toBe("사용자의 이미지를 분석하는 중이에요");
    expect(copy.loop).toContain("사진에서 광고에 쓸 핵심 요소를 찾고 있어요");
  });

  it("uses reference-aware copy when the chat has a reference image", () => {
    const copy = resolveWaitingStatusCopy({
      context: "chat_analysis",
      state: {
        referenceImagePath: "data/uploads/reference.png",
        selectedReferenceTemplateId: null,
        sourceAssetId: null,
        sourceImagePath: null,
        generationJob: null
      }
    });

    expect(copy.title).toBe("참고 스타일을 읽고 있어요");
    expect(copy.loop).toContain("참고 이미지의 분위기와 구도를 확인하고 있어요");
  });

  it("uses image planning copy for final generation planning jobs", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation",
      generationJob: job("running", "planning", { source: "web_generation_flow" })
    });

    expect(copy.title).toBe("광고 이미지 생성 방향을 정리하고 있어요");
    expect(copy.loop).toContain("브리프를 이미지 생성 요청으로 바꾸고 있어요");
  });

  it("uses image generation copy for modal and t2i stages", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation",
      generationJob: job("running", "modal_running", { source: "web_generation_flow" })
    });

    expect(copy.title).toBe("광고 이미지를 생성하는 중이에요");
    expect(copy.loop).toContain("선택한 모델이 광고 이미지를 만들고 있어요");
  });

  it("uses answer processing copy after a generation job question is answered", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation_answer",
      generationJob: job("running", "planning")
    });

    expect(copy.title).toBe("답변을 반영하고 있어요");
    expect(copy.description).toBe("방금 보낸 답변을 작업 브리프와 생성 흐름에 반영하고 있어요.");
  });
});
