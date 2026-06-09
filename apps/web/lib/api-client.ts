import type {
  ChatBrief,
  CopyCandidateOrigin,
  CopyGenerationMode,
  CopyOption,
  CustomCopyFields,
  InferredContext,
  ImageGenerationEngineFields,
  OptionQuestion,
  PartialInferredContext,
  ReferenceImageFields,
  ReferenceTemplateFields
} from "@/types/marketing";

const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "http://127.0.0.1:4000");

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function buildBffUrl(path: string): string {
  return `${BFF_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export type ChatStartResponse = {
  type?: "copy_candidates";
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  copyCandidates: CopyOption[];
  recommendedCopyId?: string | null;
  copyCandidateOrigin?: CopyCandidateOrigin;
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
  generationJob?: GenerationJob;
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

export type GenerationStartOptions = CustomCopyFields & ReferenceTemplateFields & ReferenceImageFields & ImageGenerationEngineFields & {
  copyGenerationMode?: CopyGenerationMode;
  adFormat?: string;
  renderProfile?: string;
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

export type ReferenceTemplateDetailResponse = {
  template: ReferenceTemplateCard;
  detail: Record<string, unknown>;
  similarTemplates: ReferenceTemplateCard[];
};

export type ReferenceTemplateSimilarResponse = {
  templateId: string;
  items: ReferenceTemplateCard[];
};

export type PhotoUploadResponse = {
  sourceImagePath: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
};

export type ReferenceImageUploadResponse = {
  referenceImagePath: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
};

export type ReferenceQueryParams = Record<string, string | number | boolean | string[] | undefined | null>;
export type BrandKitPayload = Record<string, unknown>;
export interface GenerationJobCreateInput {
  userInput: string;
  threadId?: string | null;
  brandKitId?: string | null;
  entryMode?: string;
  selectedReferenceTemplateId?: string | null;
  sourceImagePath?: string | null;
  referenceImagePath?: string | null;
  copyGenerationMode?: string | null;
  selectedCopyId?: string | null;
  selectedChannelId?: string | null;
  selectedTone?: string | null;
  customDirection?: string | null;
  userCustomHeadline?: string | null;
  userCustomSubcopy?: string | null;
  userPlan?: string;
  adFormat?: string | null;
  runMode?: string;
  metadata?: Record<string, unknown>;
}

export type GenerationJobAnswerPayload = {
  field?: string;
  value?: string;
  customText?: string;
  displayText?: string;
  selectedCopyId?: string;
  userCustomHeadline?: string;
  userCustomSubcopy?: string;
  payload?: Record<string, unknown>;
};

export type GenerationJobStatus = "queued" | "running" | "done" | "failed" | string;

export interface GenerationProgress {
  progress_percent: number;
  current_stage: string;
  message?: string | null;
}

export type ResultQualityDecision = "pass" | "manual_review" | "unavailable" | "retry_image" | "retry_layout" | "reject" | string;

export type ResultCompliancePayload = {
  status?: "pass" | "rewritten" | "blocked" | "needs_review" | string;
  summary?: string | null;
  findings?: unknown[];
};

export interface ResultArtifactPayload {
  schema_version?: "result_artifact_v1" | string;
  job_id?: string;
  output_dir?: string | null;
  background_image_path?: string | null;
  final_image_path?: string | null;
  download_path?: string | null;
  metadata_path?: string | null;
  prompt_path?: string | null;
  validation_path?: string | null;
  copy_path?: string | null;
  layout_path?: string | null;
  render_result_path?: string | null;
  final_image_url?: string | null;
  download_url?: string | null;
  preview_image_url?: string | null;
  copy_visual_preview_url?: string | null;
  copy_visual_preview_path?: string | null;
  prompt_summary?: Record<string, unknown> | null;
  validation_summary?: Record<string, unknown> | null;
  copy_summary?: Record<string, unknown> | null;
  layout_summary?: Record<string, unknown> | null;
  render_summary?: Record<string, unknown> | null;
  ocr_gate?: Record<string, unknown> | null;
  qualityDecision?: ResultQualityDecision | null;
  requiresManualReview?: boolean | null;
  qualityRejected?: boolean | null;
  compliance?: ResultCompliancePayload | null;
  has_text_overlay?: boolean;
  engine?: string;
  render_mode?: string;
  [key: string]: unknown;
}

export interface GenerationJob {
  job_id: string;
  thread_id?: string | null;
  status: GenerationJobStatus;
  progress?: GenerationProgress;
  progress_percent?: number | null;
  current_stage?: string | null;
  output_path?: string | null;
  result_payload?: ResultArtifactPayload | null;
  error?: unknown;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface GenerationJobResponse {
  success: true;
  job: GenerationJob;
}

export type ArchiveItemStatus = "generating" | "saved" | "favorite" | "failed";
export type ArchiveItemSource = "generated" | "reference_template" | "uploaded";

export interface ArchiveItem {
  adId: string;
  jobId?: string | null;
  title: string;
  thumbnailUrl?: string | null;
  imageUrl?: string | null;
  status: ArchiveItemStatus;
  adFormat?: string | null;
  platform?: string | null;
  source: string;
  createdAt?: string | null;
  savedAt?: string | null;
  metadata: Record<string, unknown>;
}

export interface ArchiveItemCreateInput {
  title: string;
  publicJobId?: string | null;
  thumbnailUrl?: string | null;
  imageUrl?: string | null;
  status?: Exclude<ArchiveItemStatus, "generating">;
  adFormat?: string | null;
  platform?: string | null;
  source?: ArchiveItemSource;
  workspaceId?: string | null;
  userId?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ArchiveListResponse {
  items: ArchiveItem[];
  pagination: {
    limit: number;
    offset: number;
    total: number;
    hasMore: boolean;
  };
}

export interface ArchiveMutationResponse {
  item: ArchiveItem;
}

type RawArchiveItem = {
  ad_id: string;
  job_id?: string | null;
  title: string;
  thumbnail_url?: string | null;
  image_url?: string | null;
  status?: ArchiveItemStatus;
  ad_format?: string | null;
  platform?: string | null;
  source?: string;
  created_at?: string | null;
  saved_at?: string | null;
  metadata?: Record<string, unknown>;
};

type RawArchiveListResponse = {
  items?: RawArchiveItem[];
  pagination?: {
    limit?: number;
    offset?: number;
    total?: number;
    has_more?: boolean;
  };
};

type RawArchiveMutationResponse = {
  item: RawArchiveItem;
};

type RequestHeaders = Record<string, string>;

async function getSupabaseAuthorizationHeader(): Promise<RequestHeaders> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const { createSupabaseBrowserClient } = await import("./supabase/browser");
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      return {};
    }
    const {
      data: { session }
    } = await supabase.auth.getSession();
    return session?.access_token ? { authorization: `Bearer ${session.access_token}` } : {};
  } catch {
    return {};
  }
}

async function postJson<TResponse>(path: string, body: unknown, headers: RequestHeaders = {}): Promise<TResponse> {
  const response = await fetch(buildBffUrl(path), {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeApiErrorMessage(payload?.message || payload?.error || "API request failed"));
  }
  return payload as TResponse;
}

async function deleteJson<TResponse>(path: string, params?: ReferenceQueryParams, headers: RequestHeaders = {}): Promise<TResponse> {
  const url = new URL(buildBffUrl(path));
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const response = await fetch(url.toString(), {
    method: "DELETE",
    headers: { accept: "application/json", ...headers }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeApiErrorMessage(payload?.message || payload?.error || "API request failed"));
  }
  return payload as TResponse;
}

function compactPayload(payload: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined && value !== null));
}

async function getJson<TResponse>(path: string, params?: ReferenceQueryParams, headers: RequestHeaders = {}): Promise<TResponse> {
  const url = new URL(buildBffUrl(path));
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

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { accept: "application/json", ...headers }
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeApiErrorMessage(payload?.message || payload?.error || "API request failed"));
  }
  return payload as TResponse;
}

async function patchJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(buildBffUrl(path), {
    method: "PATCH",
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
  if (message.includes("Request body is too large") || message.includes("Payload Too Large")) {
    return "사진 용량이 너무 커요. 더 작은 사진으로 다시 시도해주세요.";
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
    adFormat: options.adFormat ?? "instagram_feed",
    renderProfile: options.renderProfile ?? "premium_api",
    copyGenerationMode: options.copyGenerationMode ?? undefined,
    userCustomHeadline: options.userCustomHeadline ?? undefined,
    userCustomSubcopy: options.userCustomSubcopy ?? undefined,
    selectedReferenceTemplateId: options.selectedReferenceTemplateId ?? undefined,
    referenceImagePath: options.referenceImagePath ?? undefined
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

export async function uploadReferenceAsset(file: File): Promise<ReferenceImageUploadResponse> {
  const upload = await uploadPhotoAsset(file);
  return {
    referenceImagePath: upload.sourceImagePath,
    fileName: upload.fileName,
    mimeType: upload.mimeType,
    sizeBytes: upload.sizeBytes
  };
}

export function startPhotoGeneration(input: {
  userInput: string;
  sourceImagePath: string;
  referenceImagePath?: string | null;
  adFormat?: string;
  renderProfile?: string;
  copyGenerationMode?: CopyGenerationMode;
  userCustomHeadline?: string;
  userCustomSubcopy?: string;
  selectedReferenceTemplateId?: string | null;
}): Promise<ChatTurnResponse> {
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api",
    copyGenerationMode: input.copyGenerationMode ?? undefined,
    userCustomHeadline: input.userCustomHeadline ?? undefined,
    userCustomSubcopy: input.userCustomSubcopy ?? undefined,
    selectedReferenceTemplateId: input.selectedReferenceTemplateId ?? undefined,
    referenceImagePath: input.referenceImagePath ?? undefined
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

type RawReferenceTemplateDetailResponse = {
  template: RawReferenceTemplateCard;
  detail?: Record<string, unknown>;
  similar_templates?: RawReferenceTemplateCard[];
};

type RawReferenceTemplateSimilarResponse = {
  template_id: string;
  items?: RawReferenceTemplateCard[];
};

export function listReferenceTemplates(params: {
  keyword?: string;
  category?: string;
  tags?: string[];
  limit?: number;
} = {}): Promise<ReferenceTemplateListResponse> {
  const search = new URLSearchParams();
  if (params.keyword?.trim()) {
    search.set("keyword", params.keyword.trim());
  }
  if (params.category?.trim()) {
    search.set("category", params.category.trim());
  }
  params.tags?.forEach((tag) => {
    const trimmed = tag.trim();
    if (trimmed) {
      search.append("tags", trimmed);
    }
  });
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
    return buildBffUrl(url.replace("/api/v1/references", "/api/references"));
  }
  if (url.startsWith("/api/references/")) {
    return buildBffUrl(url);
  }
  return url;
}

export function fetchReferences(params?: ReferenceQueryParams): Promise<unknown> {
  return getJson("/api/references", params);
}

export function fetchReferenceDetail(templateId: string): Promise<ReferenceTemplateDetailResponse> {
  return getJson<RawReferenceTemplateDetailResponse>(`/api/references/${encodeURIComponent(templateId)}`).then((payload) => ({
    template: mapReferenceTemplateCard(payload.template),
    detail: payload.detail ?? {},
    similarTemplates: (payload.similar_templates ?? []).map(mapReferenceTemplateCard)
  }));
}

export function fetchSimilarReferences(templateId: string, params?: ReferenceQueryParams): Promise<ReferenceTemplateSimilarResponse> {
  return getJson<RawReferenceTemplateSimilarResponse>(`/api/references/${encodeURIComponent(templateId)}/similar`, params).then((payload) => ({
    templateId: payload.template_id,
    items: (payload.items ?? []).map(mapReferenceTemplateCard)
  }));
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

export async function createGenerationJob(payload: GenerationJobCreateInput): Promise<GenerationJobResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<GenerationJobResponse>("/api/generation-jobs", payload, authHeaders);
}

export function getGenerationJob(jobId: string): Promise<GenerationJobResponse> {
  return getJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}`);
}

export async function answerGenerationJob(jobId: string, payload: GenerationJobAnswerPayload): Promise<GenerationJobResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<GenerationJobResponse>(
    `/api/generation-jobs/${encodeURIComponent(jobId)}/answer`,
    compactPayload(payload),
    authHeaders
  );
}

export async function saveArchiveItem(input: ArchiveItemCreateInput): Promise<ArchiveMutationResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<RawArchiveMutationResponse>("/api/archive/items", {
    title: input.title,
    publicJobId: input.publicJobId ?? undefined,
    thumbnailUrl: input.thumbnailUrl ?? undefined,
    imageUrl: input.imageUrl ?? undefined,
    status: input.status ?? "saved",
    adFormat: input.adFormat ?? undefined,
    platform: input.platform ?? undefined,
    source: input.source ?? "generated",
    workspaceId: input.workspaceId ?? undefined,
    userId: input.userId ?? undefined,
    metadata: input.metadata ?? undefined
  }, authHeaders).then((payload) => ({ item: mapArchiveItem(payload.item) }));
}

export async function listArchiveItems(params: {
  workspaceId?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ArchiveListResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<RawArchiveListResponse>("/api/archive/items", {
    workspace_id: params.workspaceId,
    limit: params.limit,
    offset: params.offset
  }, authHeaders).then((payload) => ({
    items: (payload.items ?? []).map(mapArchiveItem),
    pagination: {
      limit: payload.pagination?.limit ?? params.limit ?? 50,
      offset: payload.pagination?.offset ?? params.offset ?? 0,
      total: payload.pagination?.total ?? payload.items?.length ?? 0,
      hasMore: payload.pagination?.has_more ?? false
    }
  }));
}

export async function deleteArchiveItem(archiveItemId: string, params?: { workspaceId?: string }): Promise<ArchiveMutationResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return deleteJson<RawArchiveMutationResponse>(`/api/archive/items/${encodeURIComponent(archiveItemId)}`, {
    workspace_id: params?.workspaceId
  }, authHeaders).then((payload) => ({ item: mapArchiveItem(payload.item) }));
}

function mapArchiveItem(item: RawArchiveItem): ArchiveItem {
  return {
    adId: item.ad_id,
    jobId: item.job_id,
    title: item.title,
    thumbnailUrl: item.thumbnail_url,
    imageUrl: item.image_url,
    status: item.status ?? "saved",
    adFormat: item.ad_format,
    platform: item.platform,
    source: item.source ?? "generated",
    createdAt: item.created_at,
    savedAt: item.saved_at,
    metadata: item.metadata ?? {}
  };
}

// --- Chat Thread API ---

export interface ChatThreadResponse {
  thread_id: string;
  title?: string | null;
  status: string;
  brand_kit_id?: string | null;
  project_id?: string | null;
  final_brief: Record<string, unknown>;
  active_job_id?: string | null;
  has_final_output: boolean;
  last_message_at: string;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageResponse {
  message_id: string;
  thread_id: string;
  sequence_no: number;
  role: "user" | "assistant" | "system";
  content?: string | null;
  payload: Record<string, unknown>;
  created_by?: string | null;
  job_id?: string | null;
  event_type?: string | null;
  created_at: string;
}

export interface ChatThreadListResponse {
  success: true;
  threads: ChatThreadResponse[];
  total: number;
}

export interface ChatThreadGetResponse {
  success: true;
  thread: ChatThreadResponse;
}

export interface ChatMessageListResponse {
  success: true;
  messages: ChatMessageResponse[];
  total: number;
}

export interface ChatStateSnapshotResponse {
  snapshot_id: string;
  thread_id: string;
  job_id?: string | null;
  source_message_id?: string | null;
  parent_snapshot_id?: string | null;
  snapshot_version: number;
  schema_version: number;
  snapshot_kind: string;
  state_payload: Record<string, unknown>;
  changed_fields: string[];
  selected_reference_template_id?: string | null;
  reference_template_snapshot: Record<string, unknown>;
  brand_kit_snapshot: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ChatThreadStateGetResponse {
  success: true;
  snapshot: ChatStateSnapshotResponse | null;
  meta?: Record<string, unknown>;
}

export async function listChatThreads(params: { limit?: number; offset?: number } = {}): Promise<ChatThreadListResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadListResponse>("/api/chat-threads", {
    limit: params.limit,
    offset: params.offset
  }, authHeaders);
}

export async function getChatThread(threadId: string): Promise<ChatThreadGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadGetResponse>(`/api/chat-threads/${encodeURIComponent(threadId)}`, undefined, authHeaders);
}

export async function getChatThreadMessages(threadId: string, params: { limit?: number; offset?: number } = {}): Promise<ChatMessageListResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatMessageListResponse>(`/api/chat-threads/${encodeURIComponent(threadId)}/messages`, {
    limit: params.limit,
    offset: params.offset
  }, authHeaders);
}

export async function getChatThreadState(threadId: string): Promise<ChatThreadStateGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadStateGetResponse>(`/api/chat-threads/${encodeURIComponent(threadId)}/state`, undefined, authHeaders);
}

export async function archiveChatThread(threadId: string): Promise<ChatThreadGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<ChatThreadGetResponse>(`/api/chat-threads/${encodeURIComponent(threadId)}/archive`, {}, authHeaders);
}
