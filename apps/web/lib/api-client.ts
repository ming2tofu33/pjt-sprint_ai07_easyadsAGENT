import type {
  ChatBrief,
  CopyGenerationMode,
  CopyOption,
  CustomCopyFields,
  InferredContext,
  OptionQuestion,
  PartialInferredContext,
  ReferenceTemplateFields
} from "@/types/marketing";

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

export type GenerationStartOptions = CustomCopyFields & ReferenceTemplateFields & {
  copyGenerationMode?: CopyGenerationMode;
};

export type ReferenceTemplateCard = {
  templateId: string;
  title: string;
  description?: string | null;
  category: string;
  tags: string[];
  businessTypes: string[];
  adFormats: string[];
  platforms: string[];
  aspectRatio?: string | null;
  thumbnailUrl?: string | null;
  previewUrl?: string | null;
  styleKeywords: string[];
  colorPalette: string[];
  layoutHint?: string | null;
  typographyHint?: string | null;
  popularityScore: number;
  isSaved: boolean;
};

export type ReferenceTemplateListResponse = {
  items: ReferenceTemplateCard[];
  pagination: {
    limit: number;
    offset: number;
    total: number;
    hasMore: boolean;
  };
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

async function getJson<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${BFF_BASE_URL}${path}`, {
    method: "GET",
    headers: { accept: "application/json" }
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

export function startChatGeneration(userInput: string, options: GenerationStartOptions = {}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/chat/start", {
    userInput,
    adFormat: "instagram_feed",
    renderProfile: "premium_api",
    copyGenerationMode: options.copyGenerationMode,
    userCustomHeadline: options.userCustomHeadline,
    userCustomSubcopy: options.userCustomSubcopy,
    selectedReferenceTemplateId: options.selectedReferenceTemplateId
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
  userCustomHeadline?: string;
  userCustomSubcopy?: string;
  selectedReferenceTemplateId?: string;
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api",
    copyGenerationMode: input.copyGenerationMode,
    userCustomHeadline: input.userCustomHeadline,
    userCustomSubcopy: input.userCustomSubcopy,
    selectedReferenceTemplateId: input.selectedReferenceTemplateId
  });
}

type RawReferenceTemplateCard = {
  template_id: string;
  title: string;
  description?: string | null;
  category: string;
  tags?: string[];
  business_types?: string[];
  ad_formats?: string[];
  platforms?: string[];
  aspect_ratio?: string | null;
  thumbnail_url?: string | null;
  preview_url?: string | null;
  style_keywords?: string[];
  color_palette?: string[];
  layout_hint?: string | null;
  typography_hint?: string | null;
  popularity_score?: number;
  is_saved?: boolean;
};

type RawReferenceTemplateListResponse = {
  items?: RawReferenceTemplateCard[];
  pagination?: {
    limit?: number;
    offset?: number;
    total?: number;
    has_more?: boolean;
  };
};

export function listReferenceTemplates(params: {
  keyword?: string;
  category?: string;
  limit?: number;
} = {}): Promise<ReferenceTemplateListResponse> {
  const search = new URLSearchParams();
  if (params.keyword?.trim()) {
    search.set("keyword", params.keyword.trim());
  }
  if (params.category?.trim()) {
    search.set("category", params.category.trim());
  }
  search.set("limit", String(params.limit ?? 40));
  const query = search.toString();
  return getJson<RawReferenceTemplateListResponse>(`/api/references${query ? `?${query}` : ""}`).then((payload) => ({
    items: (payload.items ?? []).map(mapReferenceTemplateCard),
    pagination: {
      limit: payload.pagination?.limit ?? params.limit ?? 40,
      offset: payload.pagination?.offset ?? 0,
      total: payload.pagination?.total ?? payload.items?.length ?? 0,
      hasMore: payload.pagination?.has_more ?? false
    }
  }));
}

function mapReferenceTemplateCard(item: RawReferenceTemplateCard): ReferenceTemplateCard {
  return {
    templateId: item.template_id,
    title: item.title,
    description: item.description,
    category: item.category,
    tags: item.tags ?? [],
    businessTypes: item.business_types ?? [],
    adFormats: item.ad_formats ?? [],
    platforms: item.platforms ?? [],
    aspectRatio: item.aspect_ratio,
    thumbnailUrl: normalizeReferenceAssetUrl(item.thumbnail_url),
    previewUrl: normalizeReferenceAssetUrl(item.preview_url),
    styleKeywords: item.style_keywords ?? [],
    colorPalette: item.color_palette ?? [],
    layoutHint: item.layout_hint,
    typographyHint: item.typography_hint,
    popularityScore: item.popularity_score ?? 0,
    isSaved: item.is_saved ?? false
  };
}

function normalizeReferenceAssetUrl(url?: string | null): string | null {
  if (!url) {
    return null;
  }
  if (url.startsWith("/api/v1/references/temp-assets/")) {
    return `${BFF_BASE_URL}${url.replace("/api/v1/references", "/api/references")}`;
  }
  if (url.startsWith("/api/references/")) {
    return `${BFF_BASE_URL}${url}`;
  }
  return url;
}
