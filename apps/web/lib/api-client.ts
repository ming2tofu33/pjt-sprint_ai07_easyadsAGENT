import type { ChatBrief, CopyOption, InferredContext, OptionQuestion, PartialInferredContext } from "@/types/marketing";

const BFF_BASE_URL = process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000";

export type ChatStartResponse = {
  type?: "copy_candidates";
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  copyCandidates: CopyOption[];
  recommendedCopyId?: string | null;
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

export type ChatTurnResponse = ChatStartResponse | ChatQuestionResponse;

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
    throw new Error(payload?.message || payload?.error || "API request failed");
  }
  return payload as TResponse;
}

async function getJson<TResponse>(path: string, params?: Record<string, string | number | boolean | string[] | undefined | null>): Promise<TResponse> {
  const url = new URL(`${BFF_BASE_URL}${path}`);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, item));
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const response = await fetch(url.toString(), { method: "GET" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || "API request failed");
  }
  return payload as TResponse;
}

async function patchJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(`${BFF_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || "API request failed");
  }
  return payload as TResponse;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result)));
    reader.addEventListener("error", () => reject(new Error("사진 파일을 읽지 못했습니다.")));
    reader.readAsDataURL(file);
  });
}

export function startChatGeneration(userInput: string): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/chat/start", {
    userInput,
    adFormat: "instagram_feed",
    renderProfile: "premium_api"
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
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api"
  });
}

export type ReferenceQueryParams = Record<string, string | number | boolean | string[] | undefined | null>;
export type BrandKitPayload = Record<string, unknown>;
export type GenerationJobPayload = Record<string, unknown>;

export function fetchReferences(params?: ReferenceQueryParams): Promise<unknown> {
  return getJson("/api/references", params);
}

export function fetchReferenceDetail(templateId: string): Promise<unknown> {
  return getJson(`/api/references/${encodeURIComponent(templateId)}`);
}

export function fetchSimilarReferences(templateId: string, params?: ReferenceQueryParams): Promise<unknown> {
  return getJson(`/api/references/${encodeURIComponent(templateId)}/similar`, params);
}

export function getCurrentBrandKit(params?: { userId?: string }): Promise<unknown> {
  return getJson("/api/brand-kits/current", params?.userId ? { user_id: params.userId } : undefined);
}

export function createBrandKit(payload: BrandKitPayload): Promise<unknown> {
  return postJson("/api/brand-kits", payload);
}

export function getBrandKit(brandKitId: string): Promise<unknown> {
  return getJson(`/api/brand-kits/${encodeURIComponent(brandKitId)}`);
}

export function updateBrandKit(brandKitId: string, payload: BrandKitPayload): Promise<unknown> {
  return patchJson(`/api/brand-kits/${encodeURIComponent(brandKitId)}`, payload);
}

export function createGenerationJob(payload: GenerationJobPayload): Promise<unknown> {
  return postJson("/api/generation-jobs", payload);
}

export function getGenerationJob(jobId: string): Promise<unknown> {
  return getJson(`/api/generation-jobs/${encodeURIComponent(jobId)}`);
}
