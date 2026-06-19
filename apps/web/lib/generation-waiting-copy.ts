import type { GenerationJob } from "@/lib/api-client";
import type { ChatFlowState } from "@/types/marketing";

export type WaitingStatusContext =
  | "chat_analysis"
  | "brief_refinement"
  | "photo_upload"
  | "generation"
  | "generation_answer"
  | "result_pending";

export type WaitingStatusCopy = {
  statusKey: string;
  eyebrow: string;
  title: string;
  description: string;
  loop: readonly string[];
};

type WaitingStateInput = Partial<
  Pick<
    ChatFlowState,
    | "generationJob"
    | "referenceAssetId"
    | "selectedReferenceTemplateId"
    | "sourceAssetId"
    | "copyGenerationMode"
  >
>;

type ResolveWaitingCopyInput = {
  context: WaitingStatusContext;
  state?: WaitingStateInput | null;
  generationJob?: GenerationJob | null;
};

const chatAnalysisCopy: WaitingStatusCopy = {
  statusKey: "chat_analysis",
  eyebrow: "요청 분석",
  title: "요청 내용을 분석하고 있어요",
  description: "입력한 내용을 읽고 광고 제작에 필요한 정보를 정리하고 있어요.",
  loop: ["요청 문장에서 업종과 상품을 찾고 있어요", "부족한 정보가 있는지 확인하고 있어요", "다음 질문을 준비하고 있어요"]
};

const referenceAnalysisCopy: WaitingStatusCopy = {
  statusKey: "reference_analysis",
  eyebrow: "샘플 분석",
  title: "참고 스타일을 읽고 있어요",
  description: "선택한 샘플이나 참고 이미지의 분위기를 광고 요청에 연결하고 있어요.",
  loop: ["참고 이미지의 분위기와 구도를 확인하고 있어요", "광고에 반영할 스타일 힌트를 정리하고 있어요", "요청 내용과 참고 스타일을 맞춰보고 있어요"]
};

const photoAnalysisCopy: WaitingStatusCopy = {
  statusKey: "photo_analysis",
  eyebrow: "사진 분석",
  title: "사용자의 이미지를 분석하는 중이에요",
  description: "올린 사진에서 광고에 사용할 요소와 이미지 생성 방향을 찾고 있어요.",
  loop: ["사진에서 광고에 쓸 핵심 요소를 찾고 있어요", "상품이 잘 보이도록 이미지 방향을 정리하고 있어요", "사진과 요청 내용을 함께 확인하고 있어요"]
};

const briefCopy: WaitingStatusCopy = {
  statusKey: "brief_refinement",
  eyebrow: "브리프 정리",
  title: "작업 브리프를 완성하고 있어요",
  description: "선택한 문구, 채널, 분위기를 바탕으로 이미지 생성 전 브리프를 정리하고 있어요.",
  loop: ["광고 목적과 상품 정보를 정리하고 있어요", "이미지에 들어갈 문구를 확인하고 있어요", "생성 요청에 맞는 브리프를 만들고 있어요"]
};

const answerCopy: WaitingStatusCopy = {
  statusKey: "generation_answer",
  eyebrow: "답변 반영",
  title: "답변을 반영하고 있어요",
  description: "방금 보낸 답변을 작업 브리프와 생성 흐름에 반영하고 있어요.",
  loop: ["답변 내용을 작업 상태에 저장하고 있어요", "다음 생성 단계를 다시 확인하고 있어요", "필요한 경우 다음 질문을 준비하고 있어요"]
};

const imagePlanningCopy: WaitingStatusCopy = {
  statusKey: "image_planning",
  eyebrow: "이미지 준비",
  title: "광고 이미지 생성 방향을 정리하고 있어요",
  description: "확정된 브리프를 이미지 생성 모델이 이해할 수 있는 요청으로 바꾸고 있어요.",
  loop: ["브리프를 이미지 생성 요청으로 바꾸고 있어요", "스타일과 구도 힌트를 정리하고 있어요", "광고 이미지에 필요한 문구와 여백을 확인하고 있어요"]
};

const imageGeneratingCopy: WaitingStatusCopy = {
  statusKey: "image_generating",
  eyebrow: "이미지 생성",
  title: "광고 이미지를 생성하는 중이에요",
  description: "선택한 이미지 모델이 브리프와 스타일 힌트를 바탕으로 광고 이미지를 만들고 있어요.",
  loop: ["선택한 모델이 광고 이미지를 만들고 있어요", "스타일과 구도를 이미지에 반영하고 있어요", "완성된 이미지 품질을 확인할 준비를 하고 있어요"]
};

const storageCopy: WaitingStatusCopy = {
  statusKey: "storage_pending",
  eyebrow: "저장 확인",
  title: "보관함 연결을 확인하고 있어요",
  description: "완성된 이미지를 보관함에서 열 수 있도록 저장 정보를 확인하고 있어요.",
  loop: ["완성된 이미지 주소를 확인하고 있어요", "보관함에 연결할 정보를 정리하고 있어요", "결과 화면에 보여줄 정보를 준비하고 있어요"]
};

const failedCopy: WaitingStatusCopy = {
  statusKey: "failed",
  eyebrow: "오류 확인",
  title: "생성 상태를 확인하고 있어요",
  description: "작업 중 문제가 생겼는지 확인하고 다시 시도할 수 있는 상태로 정리하고 있어요.",
  loop: ["오류 내용을 확인하고 있어요", "입력 내용을 유지한 채 복구할 방법을 찾고 있어요"]
};

export function waitingMessageAt(messages: readonly string[], tick: number): string {
  if (messages.length === 0) {
    return "";
  }
  const safeTick = Number.isFinite(tick) ? Math.max(0, Math.floor(tick)) : 0;
  return messages[safeTick % messages.length] ?? messages[0] ?? "";
}

export function resolveWaitingStatusCopy(input: ResolveWaitingCopyInput): WaitingStatusCopy {
  const state = input.state ?? null;
  const job = input.generationJob ?? state?.generationJob ?? null;
  const status = normalize(job?.status);
  const stage = normalize(job?.progress?.current_stage ?? job?.current_stage ?? job?.status);

  if (status === "failed" || stage === "failed") {
    return failedCopy;
  }

  if (input.context === "photo_upload") {
    return photoAnalysisCopy;
  }

  if (input.context === "brief_refinement") {
    return briefCopy;
  }

  if (input.context === "generation_answer") {
    return answerCopy;
  }

  if (status === "done" || status === "completed" || stage === "completed") {
    return storageCopy;
  }

  if (input.context === "result_pending") {
    return isImageStage(stage) ? imageGeneratingCopy : storageCopy;
  }

  if (isImageStage(stage)) {
    return imageGeneratingCopy;
  }

  const isFinalGeneration = isFinalImageGenerationJob(job) || input.context === "generation";
  if (isFinalGeneration) {
    return imagePlanningCopy;
  }

  if (hasSourcePhoto(state)) {
    return photoAnalysisCopy;
  }

  if (hasReference(state)) {
    return referenceAnalysisCopy;
  }

  return chatAnalysisCopy;
}

function normalize(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function isFinalImageGenerationJob(job: GenerationJob | null | undefined): boolean {
  const metadata = asRecord(job?.metadata);
  const finalBrief = asRecord(metadata.final_brief ?? metadata.finalBrief);
  return metadata.source === "web_generation_flow" || Object.keys(finalBrief).length > 0;
}

function hasSourcePhoto(state: WaitingStateInput | null): boolean {
  return Boolean(state?.sourceAssetId);
}

function hasReference(state: WaitingStateInput | null): boolean {
  return Boolean(state?.referenceAssetId || state?.selectedReferenceTemplateId);
}

function isImageStage(stage: string): boolean {
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
