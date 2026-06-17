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
  ProgressState,
  ReferenceImageFields,
  ReferenceTemplateFields
} from "@/types/marketing";
import { getGenerationEngineOption, resolveGenerationEnginePreference } from "@/lib/generation-engine";
import { getSupabaseAuthorizationHeader, type RequestHeaders } from "@/lib/supabase/session";
import { estimateJsonSizeBytes, measureWebPerf, perfTraceEnabled, recordWebPerfEvent } from "@/lib/performance";

const BFF_BASE_URL = normalizeBaseUrl(process.env.NEXT_PUBLIC_BFF_BASE_URL || "");

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function buildBffUrl(path: string): string {
  return `${BFF_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function recordRenderMark(markName: string) {
  if (!perfTraceEnabled() || typeof window === "undefined") {
    return;
  }
  performance.mark(markName);
  recordWebPerfEvent({
    schema_version: 1,
    event_type: "frontend_render_mark",
    component: "web",
    operation: markName,
    started_at: new Date().toISOString(),
    duration_ms: 0,
    status: "ok",
    metadata: {}
  });
}

function buildBffUrlWithParams(path: string, params?: ReferenceQueryParams): string {
  const base =
    BFF_BASE_URL ||
    (typeof window !== "undefined" && window.location?.origin ? window.location.origin : "http://localhost");
  const url = new URL(buildBffUrl(path), base);
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
  if (BFF_BASE_URL) {
    return url.toString();
  }
  return `${url.pathname}${url.search}`;
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
  selectedChannelId?: string | null;
};

export type ChatQuestionResponse = {
  type: "option_question";
  jobId: string;
  threadId: string;
  status: string;
  context: PartialInferredContext;
  question: OptionQuestion;
  progress?: ProgressState | null;
  missingFields?: string[];
  generationJob?: GenerationJob;
  selectedChannelId?: string | null;
};

export type ChatBriefReadyResponse = {
  type: "brief_ready";
  jobId: string;
  threadId: string;
  status: string;
  context: InferredContext;
  brief: ChatBrief;
  copyGenerationMode: CopyGenerationMode;
  selectedChannelId?: string | null;
};

export type ChatTurnResponse = ChatStartResponse | ChatQuestionResponse | ChatBriefReadyResponse;

export type ChatBriefResponse = {
  jobId: string;
  threadId: string;
  status: string;
  brief: ChatBrief;
  selectedChannelId?: string | null;
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
  sourceAssetId?: string | null;
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

export type AssetUploadResponse = {
  assetId: string;
  kind: "upload" | "source" | "reference" | string;
  status: "pending" | "ready" | "failed" | string;
  imageUrl?: string | null;
  mimeType?: string | null;
  sizeBytes?: number | null;
  width?: number | null;
  height?: number | null;
  storageProvider?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type AdminReferenceTemplate = ReferenceTemplateCard & {
  width?: number | null;
  height?: number | null;
  status?: "active" | "inactive" | "draft" | string;
  source?: string | null;
  licenseNote?: string | null;
  metadata?: Record<string, unknown>;
};

export type AdminReferenceTemplateCreateInput = {
  assetId: string;
  title: string;
  description?: string | null;
  category: string;
  subCategory?: string | null;
  tags?: string[];
  businessTypes?: string[];
  adFormats?: string[];
  platforms?: string[];
  aspectRatio?: string | null;
  styleKeywords?: string[];
  colorPalette?: string[];
  layoutHint?: string | null;
  typographyHint?: string | null;
  backgroundStyle?: string | null;
  popularityScore?: number;
  status?: "active" | "inactive" | "draft";
  licenseNote?: string | null;
  copyrightStatus?: string;
  metadata?: Record<string, unknown>;
};

export type ReferenceQueryParams = Record<string, string | number | boolean | string[] | undefined | null>;
export type BrandKitPayload = Record<string, unknown>;
export interface GenerationJobCreateInput {
  userInput: string;
  threadId?: string | null;
  continuationMode?: "new_thread" | "new_turn" | "retry_failed" | "regenerate_from_output";
  brandKitId?: string | null;
  entryMode?: string;
  selectedReferenceTemplateId?: string | null;
  sourceAssetId?: string | null;
  referenceAssetId?: string | null;
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
  action?: string;
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
  status?:
    | "pass"
    | "rewritten"
    | "rewritten_by_user_choice"
    | "blocked"
    | "block"
    | "needs_review"
    | "manual_review_required"
    | "evidence_required"
    | "warn"
    | string;
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
  outputId?: string | null;
  title: string;
  thumbnailUrl?: string | null;
  imageUrl?: string | null;
  downloadUrl?: string | null;
  status: ArchiveItemStatus;
  adFormat?: string | null;
  platform?: string | null;
  source: string;
  storageProvider?: string | null;
  mimeType?: string | null;
  width?: number | null;
  height?: number | null;
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
  output_id?: string | null;
  title: string;
  thumbnail_url?: string | null;
  image_url?: string | null;
  download_url?: string | null;
  status?: ArchiveItemStatus;
  ad_format?: string | null;
  platform?: string | null;
  source?: string;
  storage_provider?: string | null;
  mime_type?: string | null;
  width?: number | null;
  height?: number | null;
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

async function postJson<TResponse>(path: string, body: unknown, headers: RequestHeaders = {}): Promise<TResponse> {
  return measureWebPerf(
    "frontend_request",
    `POST ${path}`,
    async (span) => {
      const response = await fetch(buildBffUrl(path), {
        method: "POST",
        headers: { "content-type": "application/json", ...headers },
        body: JSON.stringify(body)
      });
      const payload = await response.json().catch(() => ({}));
      span.addMetadata({
        request_size_bytes: estimateJsonSizeBytes(body),
        response_size_bytes: estimateJsonSizeBytes(payload),
        response_size_method: "json_estimate"
      });
      if (!response.ok) {
        throw apiErrorFrom(response, payload);
      }
      return payload as TResponse;
    },
    { route_template: path, method: "POST" }
  );
}

async function deleteJson<TResponse>(path: string, params?: ReferenceQueryParams, headers: RequestHeaders = {}): Promise<TResponse> {
  const url = buildBffUrlWithParams(path, params);
  return measureWebPerf(
    "frontend_request",
    `DELETE ${path}`,
    async (span) => {
      const response = await fetch(url, {
        method: "DELETE",
        headers: { accept: "application/json", ...headers }
      });
      const payload = await response.json().catch(() => ({}));
      span.addMetadata({
        response_size_bytes: estimateJsonSizeBytes(payload),
        response_size_method: "json_estimate"
      });
      if (!response.ok) {
        throw apiErrorFrom(response, payload);
      }
      return payload as TResponse;
    },
    { route_template: path, method: "DELETE" }
  );
}

function compactPayload(payload: object): Record<string, unknown> {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== undefined && value !== null));
}

async function withRefreshedSupabaseAuthRetry<TResponse>(
  request: (headers: RequestHeaders) => Promise<TResponse>
): Promise<TResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  try {
    return await request(authHeaders);
  } catch (error) {
    if (!(error instanceof ApiError) || error.errorCode !== "invalid_or_expired_session") {
      throw error;
    }
    const refreshedHeaders = await getSupabaseAuthorizationHeader({
      allowAnonymous: false,
      forceRefresh: true
    });
    if (!refreshedHeaders.authorization || refreshedHeaders.authorization === authHeaders.authorization) {
      throw error;
    }
    return request(refreshedHeaders);
  }
}

async function getJson<TResponse>(path: string, params?: ReferenceQueryParams, headers: RequestHeaders = {}): Promise<TResponse> {
  const url = buildBffUrlWithParams(path, params);
  return measureWebPerf(
    "frontend_request",
    `GET ${path}`,
    async (span) => {
      const response = await fetch(url, {
        method: "GET",
        headers: { accept: "application/json", ...headers }
      });
      const payload = await response.json().catch(() => ({}));
      span.addMetadata({
        response_size_bytes: estimateJsonSizeBytes(payload),
        response_size_method: "json_estimate"
      });
      if (!response.ok) {
        throw apiErrorFrom(response, payload);
      }
      return payload as TResponse;
    },
    { route_template: path, method: "GET" }
  );
}

async function patchJson<TResponse>(path: string, body: unknown, headers: RequestHeaders = {}): Promise<TResponse> {
  return measureWebPerf(
    "frontend_request",
    `PATCH ${path}`,
    async (span) => {
      const response = await fetch(buildBffUrl(path), {
        method: "PATCH",
        headers: { "content-type": "application/json", ...headers },
        body: JSON.stringify(body)
      });
      const payload = await response.json().catch(() => ({}));
      span.addMetadata({
        request_size_bytes: estimateJsonSizeBytes(body),
        response_size_bytes: estimateJsonSizeBytes(payload),
        response_size_method: "json_estimate"
      });
      if (!response.ok) {
        throw apiErrorFrom(response, payload);
      }
      return payload as TResponse;
    },
    { route_template: path, method: "PATCH" }
  );
}

export class ApiError extends Error {
  errorCode?: string;
  status: number;

  constructor(message: string, options: { errorCode?: string; status: number }) {
    super(message);
    this.name = "ApiError";
    this.errorCode = options.errorCode;
    this.status = options.status;
  }
}

function apiErrorFrom(response: Response, payload: { message?: string; error?: string; error_code?: string } | null): ApiError {
  const errorCode = typeof payload?.error_code === "string" ? payload.error_code : undefined;
  const rawMessage = payload?.message || payload?.error || "API request failed";
  return new ApiError(normalizeApiErrorMessage(rawMessage, errorCode), { errorCode, status: response.status });
}

function normalizeApiErrorMessage(message: string, errorCode?: string): string {
  if (errorCode === "thread_limit_reached") {
    return "작업은 최대 3개까지만 만들 수 있어요. 새 작업을 시작하려면 기존 작업 하나를 삭제해주세요.";
  }
  if (errorCode === "upstream_orchestrator_unavailable") {
    return "생성 서버에 연결하지 못했어요. 입력 내용은 유지했으니 잠시 후 다시 시도해 주세요.";
  }
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

async function uploadLocalPhotoAsset(file: File): Promise<PhotoUploadResponse> {
  const dataUrl = await readFileAsDataUrl(file);
  return postJson<PhotoUploadResponse>("/api/generate/photo/upload", {
    filename: file.name,
    mimeType: file.type || "image/png",
    dataUrl
  });
}

export async function uploadPhotoAsset(file: File): Promise<PhotoUploadResponse> {
  const localUpload = await uploadLocalPhotoAsset(file);
  const sourceAsset = await uploadImageToR2(file, "source");
  return {
    ...localUpload,
    sourceAssetId: sourceAsset.assetId
  };
}

export async function uploadReferenceAsset(file: File): Promise<ReferenceImageUploadResponse> {
  const upload = await uploadLocalPhotoAsset(file);
  return {
    referenceImagePath: upload.sourceImagePath,
    fileName: upload.fileName,
    mimeType: upload.mimeType,
    sizeBytes: upload.sizeBytes
  };
}

function mapAssetResponse(item: RawAssetResponse): AssetUploadResponse {
  return {
    assetId: item.assetId ?? item.asset_id ?? "",
    kind: item.kind ?? "reference",
    status: item.status ?? "pending",
    imageUrl: item.imageUrl ?? item.image_url,
    mimeType: item.mimeType ?? item.mime_type,
    sizeBytes: item.sizeBytes ?? item.size_bytes,
    width: item.width,
    height: item.height,
    storageProvider: item.storageProvider ?? item.storage_provider,
    metadata: item.metadata
  };
}

async function uploadImageToR2(file: File, kind: "source" | "reference"): Promise<AssetUploadResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  const presign = await postJson<RawAssetPresignResponse>("/api/assets/uploads/presign", {
    kind,
    filename: file.name,
    mimeType: file.type || "image/png",
    sizeBytes: file.size
  }, authHeaders);
  const asset = mapAssetResponse(presign.asset);
  let uploadResponse: Response;
  try {
    uploadResponse = await fetch(presign.upload.url, {
      method: presign.upload.method,
      headers: presign.upload.headers ?? { "Content-Type": file.type || "image/png" },
      body: file
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError("이미지 스토리지 업로드가 브라우저에서 차단됐어요. R2 CORS 설정을 확인해주세요.", { status: 0 });
    }
    throw error;
  }
  if (!uploadResponse.ok) {
    throw new ApiError("레퍼런스 이미지를 스토리지에 업로드하지 못했어요.", { status: uploadResponse.status });
  }
  const complete = await postJson<RawAssetCompleteResponse>(`/api/assets/uploads/${encodeURIComponent(asset.assetId)}/complete`, {}, authHeaders);
  return mapAssetResponse(complete.asset);
}

export async function uploadReferenceImageToR2(file: File): Promise<AssetUploadResponse> {
  return uploadImageToR2(file, "reference");
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
} & ImageGenerationEngineFields): Promise<ChatTurnResponse> {
  const backendEngine = input.imageGenerationEngine ? resolveGenerationEnginePreference(input.imageGenerationEngine) : undefined;
  const engineOption = input.imageGenerationEngine ? getGenerationEngineOption(input.imageGenerationEngine) : undefined;
  return postJson<ChatTurnResponse>("/api/generate/photo/start", {
    userInput: input.userInput,
    sourceImagePath: input.sourceImagePath,
    adFormat: input.adFormat ?? "instagram_feed",
    renderProfile: input.renderProfile ?? "premium_api",
    copyGenerationMode: input.copyGenerationMode ?? undefined,
    userCustomHeadline: input.userCustomHeadline ?? undefined,
    userCustomSubcopy: input.userCustomSubcopy ?? undefined,
    selectedReferenceTemplateId: input.selectedReferenceTemplateId ?? undefined,
    referenceImagePath: input.referenceImagePath ?? undefined,
    imageGenerationEngine: input.imageGenerationEngine ?? undefined,
    requestedEngine: backendEngine,
    t2iEngine: backendEngine,
    selectedEngineLabel: engineOption?.modelName
  });
}

type RawAssetResponse = {
  assetId?: string;
  asset_id?: string;
  kind?: string;
  status?: string;
  imageUrl?: string | null;
  image_url?: string | null;
  mimeType?: string | null;
  mime_type?: string | null;
  sizeBytes?: number | null;
  size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  storageProvider?: string | null;
  storage_provider?: string | null;
  metadata?: Record<string, unknown> | null;
};

type RawAssetPresignResponse = {
  asset: RawAssetResponse;
  upload: {
    method: "PUT";
    url: string;
    headers?: Record<string, string>;
    expires_at?: string;
    expiresAt?: string;
  };
};

type RawAssetCompleteResponse = {
  success?: boolean;
  asset: RawAssetResponse;
};

type RawAdminReferenceTemplate = RawReferenceTemplateCard & {
  width?: number | null;
  height?: number | null;
  status?: string;
  source?: string | null;
  license_note?: string | null;
  metadata?: Record<string, unknown>;
};

type RawAdminReferenceListResponse = {
  success?: boolean;
  items?: RawAdminReferenceTemplate[];
};

type RawAdminReferenceItemResponse = {
  template: RawAdminReferenceTemplate;
};

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


function mapAdminReferenceTemplate(item: RawAdminReferenceTemplate): AdminReferenceTemplate {
  return {
    ...mapReferenceTemplateCard(item),
    width: item.width,
    height: item.height,
    status: item.status,
    source: item.source,
    licenseNote: item.license_note,
    metadata: item.metadata ?? {}
  };
}

export async function listAdminReferenceTemplates(params: { activeOnly?: boolean } = {}): Promise<AdminReferenceTemplate[]> {
  const authHeaders = await getSupabaseAuthorizationHeader({ allowAnonymous: false });
  return getJson<RawAdminReferenceListResponse>("/api/admin/references", {
    active_only: params.activeOnly
  }, authHeaders).then((payload) => (payload.items ?? []).map(mapAdminReferenceTemplate));
}

export async function createAdminReferenceTemplate(input: AdminReferenceTemplateCreateInput): Promise<AdminReferenceTemplate> {
  const authHeaders = await getSupabaseAuthorizationHeader({ allowAnonymous: false });
  return postJson<RawAdminReferenceItemResponse>("/api/admin/references", input, authHeaders).then((payload) => mapAdminReferenceTemplate(payload.template));
}

export async function publishAdminReferenceTemplate(templateId: string): Promise<AdminReferenceTemplate> {
  const authHeaders = await getSupabaseAuthorizationHeader({ allowAnonymous: false });
  return postJson<RawAdminReferenceItemResponse>(`/api/admin/references/${encodeURIComponent(templateId)}/publish`, {}, authHeaders).then((payload) => mapAdminReferenceTemplate(payload.template));
}

export async function unpublishAdminReferenceTemplate(templateId: string): Promise<AdminReferenceTemplate> {
  const authHeaders = await getSupabaseAuthorizationHeader({ allowAnonymous: false });
  return postJson<RawAdminReferenceItemResponse>(`/api/admin/references/${encodeURIComponent(templateId)}/unpublish`, {}, authHeaders).then((payload) => mapAdminReferenceTemplate(payload.template));
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
  const requestPayload = compactPayload(payload);
  return withRefreshedSupabaseAuthRetry((authHeaders) =>
    postJson<GenerationJobResponse>("/api/generation-jobs", requestPayload, authHeaders)
  );
}

export async function getGenerationJob(jobId: string): Promise<GenerationJobResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<GenerationJobResponse>(`/api/generation-jobs/${encodeURIComponent(jobId)}`, undefined, authHeaders);
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
  includeTotal?: boolean;
} = {}): Promise<ArchiveListResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<RawArchiveListResponse>("/api/archive/items", {
    workspace_id: params.workspaceId,
    limit: params.limit,
    offset: params.offset,
    include_total: params.includeTotal === false ? false : undefined
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

export async function getArchiveItem(archiveItemId: string, params?: { workspaceId?: string }): Promise<ArchiveItem> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<RawArchiveItem>(`/api/archive/items/${encodeURIComponent(archiveItemId)}`, {
    workspace_id: params?.workspaceId
  }, authHeaders).then(mapArchiveItem);
}

export async function updateArchiveItem(
  archiveItemId: string,
  input: { status: Exclude<ArchiveItemStatus, "generating" | "failed">; workspaceId?: string | null }
): Promise<ArchiveMutationResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return patchJson<RawArchiveMutationResponse>(`/api/archive/items/${encodeURIComponent(archiveItemId)}`, {
    status: input.status,
    workspaceId: input.workspaceId ?? undefined
  }, authHeaders).then((payload) => ({ item: mapArchiveItem(payload.item) }));
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
    outputId: item.output_id,
    title: item.title,
    thumbnailUrl: item.thumbnail_url,
    imageUrl: item.image_url,
    downloadUrl: item.download_url,
    status: item.status ?? "saved",
    adFormat: item.ad_format,
    platform: item.platform,
    source: item.source ?? "generated",
    storageProvider: item.storage_provider,
    mimeType: item.mime_type,
    width: item.width,
    height: item.height,
    createdAt: item.created_at,
    savedAt: item.saved_at,
    metadata: item.metadata ?? {}
  };
}

// --- Chat Thread API ---

export type ThreadResumeAction =
  | "continue_draft"
  | "answer_pending_job"
  | "view_result"
  | "locked_running"
  | "retry_failed_job";

export interface ChatThreadResumeState {
  action: ThreadResumeAction;
  thread_id: string;
  resume_job_id?: string | null;
  final_output_id?: string | null;
  latest_snapshot_id?: string | null;
  snapshot_kind?: string | null;
  reason?: string | null;
  current_question?: Record<string, unknown> | null;
}

export interface ChatThreadResponse {
  thread_id: string;
  title?: string | null;
  status: string;
  brand_kit_id?: string | null;
  project_id?: string | null;
  final_brief: Record<string, unknown>;
  active_job_id?: string | null;
  has_final_output: boolean;
  final_output_id?: string | null;
  resume_state?: ChatThreadResumeState | null;
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

export interface ChatThreadResumeStateGetResponse {
  success: true;
  resume_state: ChatThreadResumeState;
}

export async function listChatThreads(
  params: { limit?: number; offset?: number; includeTotal?: boolean; includeArchived?: boolean } = {}
): Promise<ChatThreadListResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadListResponse>("/api/chat-threads", {
    limit: params.limit,
    offset: params.offset,
    include_total: params.includeTotal === false ? false : undefined,
    include_archived: params.includeArchived === true ? true : undefined
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

export async function getChatThreadResumeState(threadId: string): Promise<ChatThreadResumeStateGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return getJson<ChatThreadResumeStateGetResponse>(
    `/api/chat-threads/${encodeURIComponent(threadId)}/resume-state`,
    undefined,
    authHeaders
  );
}

export type ArchiveChatThreadOptions = {
  force?: boolean;
};

export async function archiveChatThread(
  threadId: string,
  options: ArchiveChatThreadOptions = {}
): Promise<ChatThreadGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<ChatThreadGetResponse>(
    `/api/chat-threads/${encodeURIComponent(threadId)}/archive`,
    { force: options.force === true },
    authHeaders
  );
}

export async function restoreChatThread(threadId: string): Promise<ChatThreadGetResponse> {
  const authHeaders = await getSupabaseAuthorizationHeader();
  return postJson<ChatThreadGetResponse>(
    `/api/chat-threads/${encodeURIComponent(threadId)}/restore`,
    {},
    authHeaders
  );
}
