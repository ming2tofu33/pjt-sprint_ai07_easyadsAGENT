import type { GenerationJob } from "@/lib/api-client";

export type GenerationStageKey = "queued" | "planning" | "image" | "storage" | "waiting" | "completed" | "failed";

export type GenerationStageView = {
  key: GenerationStageKey;
  label: string;
  detail: string;
  activeStepIndex: number;
  isTerminal: boolean;
  isFailed: boolean;
};

export const generationStatusSteps = [
  "생성 요청 접수",
  "광고 방향 정리",
  "이미지 생성",
  "보관함 연결 확인"
] as const;

export function generationStageViewFromJob(job: GenerationJob | null | undefined): GenerationStageView {
  const status = normalizeStage(job?.status);
  const stage = normalizeStage(job?.progress?.current_stage ?? job?.current_stage ?? job?.status);

  if (status === "failed" || stage === "failed") {
    return {
      key: "failed",
      label: "생성 오류 확인 중",
      detail: "작업 중 문제가 생겼는지 확인하고 있어요.",
      activeStepIndex: 0,
      isTerminal: true,
      isFailed: true
    };
  }

  if (status === "done" || status === "completed" || stage === "done" || stage === "completed") {
    return {
      key: "completed",
      label: "보관함 연결 완료",
      detail: "완성된 이미지를 보관함에서 확인할 수 있어요.",
      activeStepIndex: 3,
      isTerminal: true,
      isFailed: false
    };
  }

  if (status === "waiting_user_input" || stage === "waiting_user_input") {
    return {
      key: "waiting",
      label: "추가 정보 확인 중",
      detail: "이미지를 만들기 전에 필요한 답변을 기다리고 있어요.",
      activeStepIndex: 1,
      isTerminal: false,
      isFailed: false
    };
  }

  if (isImageGenerationStage(stage)) {
    return {
      key: "image",
      label: "이미지 생성 중",
      detail: "선택한 모델이 광고 이미지를 만들고 있어요.",
      activeStepIndex: 2,
      isTerminal: false,
      isFailed: false
    };
  }

  if (isPlanningStage(stage) || status === "running") {
    return {
      key: "planning",
      label: "광고 방향 정리 중",
      detail: "브리프와 이미지 생성 방향을 정리하고 있어요.",
      activeStepIndex: 1,
      isTerminal: false,
      isFailed: false
    };
  }

  return {
    key: "queued",
    label: "생성 요청 접수 중",
    detail: "요청을 보내고 작업을 시작할 준비를 하고 있어요.",
    activeStepIndex: 0,
    isTerminal: false,
    isFailed: false
  };
}

function normalizeStage(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function isPlanningStage(stage: string): boolean {
  return [
    "planning",
    "brief_interpretation",
    "format_planning",
    "copy_selection",
    "copywriting",
    "prompt_planning"
  ].includes(stage);
}

function isImageGenerationStage(stage: string): boolean {
  return [
    "rendering",
    "t2i_running",
    "generating_image",
    "modal_submitted",
    "modal_running",
    "background_generation",
    "final_rendering"
  ].includes(stage);
}
