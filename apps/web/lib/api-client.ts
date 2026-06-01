import type { ChatBrief, CopyGenerationMode, CopyOption, InferredContext, OptionQuestion, PartialInferredContext } from "@/types/marketing";

const BFF_BASE_URL = process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000";

export type ChatStartResponse = {
  type?: "copy_candidates";
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  copyCandidates: CopyOption[];
  recommendedCopyId?: string | null;
  copyGenerationMode?: CopyGenerationMode;
};

export type ChatQuestionResponse = {
  type: "option_question";
  jobId: string;
  threadId: string;
  status: string;
  context: PartialInferredContext;
  question: OptionQuestion;
  missingFields?: string[];
};

export type ChatBriefReadyResponse = {
  type: "brief_ready";
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  brief: ChatBrief;
  copyGenerationMode: CopyGenerationMode;
};

export type ChatTurnResponse = ChatStartResponse | ChatQuestionResponse | ChatBriefReadyResponse;

export type ChatBriefResponse = {
  jobId: string;
  threadId: string;
  status: string;
  brief: ChatBrief;
};

export type PhotoUploadResponse = {
  sourceImagePath: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
};

async function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(`${BFF_BASE_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeApiErrorMessage(payload?.message || payload?.error || "API request failed"));
  }
  return payload as TResponse;
}

function normalizeApiErrorMessage(message: string): string {
  if (message.includes("OPENAI_API_KEY missing")) {
    return "이미지 생성 API 키가 설정되지 않았어요. OPENAI_API_KEY를 확인해주세요.";
  }
  if (message.includes("API call disabled")) {
    return "이미지 생성 API 호출이 비활성화되어 있어요. 실제 생성을 확인하려면 T2I_ALLOW_API_CALLS=true 설정이 필요합니다.";
  }
  if (message.includes("input image not found")) {
    return "업로드한 사진 파일을 생성 서버에서 찾지 못했어요. BFF_UPLOAD_DIR와 orchestrator 실행 위치를 확인해주세요.";
  }
  return message;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result)));
    reader.addEventListener("error", () => reject(new Error("사진 파일을 읽지 못했습니다.")));
    reader.readAsDataURL(file);
  });
}

export function startChatGeneration(userInput: string, options: { copyGenerationMode?: CopyGenerationMode } = {}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/chat/start", {
    userInput,
    adFormat: "instagram_feed",
    renderProfile: "premium_api",
    copyGenerationMode: options.copyGenerationMode
  });
}

export function answerChatQuestion(input: {
  jobId: string;
  threadId: string;
  field: string;
  value: string;
  customText?: string;
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/chat/answer", input);
}

export function createChatBrief(input: {
  jobId: string;
  threadId: string;
  selectedCopyId: string;
  selectedChannelId: string;
  selectedTone: string;
  customDirection: string;
}): Promise<ChatBriefResponse> {
  return postJson<ChatBriefResponse>("/api/generate/chat/brief", input);
}

export async function uploadPhotoAsset(file: File): Promise<PhotoUploadResponse> {
  const dataUrl = await readFileAsDataUrl(file);
  return postJson<PhotoUploadResponse>("/api/generate/photo/upload", {
    filename: file.name,
    mimeType: file.type || "image/png",
    dataUrl
  });
}

export function startPhotoGeneration(input: {
  userInput: string;
  sourceImagePath: string;
  adFormat?: string;
  renderProfile?: string;
  copyGenerationMode?: CopyGenerationMode;
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api",
    copyGenerationMode: input.copyGenerationMode
  });
}
