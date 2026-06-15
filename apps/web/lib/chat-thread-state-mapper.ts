import type {
  ChatFlowState,
  CopyCandidateOrigin,
  CopyGenerationMode,
  CopyOption,
  InferredContext,
  OptionQuestion
} from "@/types/marketing";
import type { ChatMessageResponse, ChatStateSnapshotResponse, GenerationJob } from "./api-client";
import { DEFAULT_IMAGE_GENERATION_ENGINE, type ImageGenerationEngine } from "./generation-engine";

export type ThreadSnapshotRestoreState = {
  prompt: string;
  jobId: string;
  threadId: string;
  context: InferredContext;
  copyGenerationMode: CopyGenerationMode;
  copyCandidates: CopyOption[];
  copyCandidateOrigin: CopyCandidateOrigin;
  selectedCopyId: string;
  selectedChannelId: string;
  selectedTone: string;
  selectedImageGenerationEngine: ImageGenerationEngine;
  customDirection: string;
  userCustomHeadline: string;
  userCustomSubcopy: string;
  sourceAssetId: string | null;
  sourceImagePath: string | null;
  referenceImagePath: string | null;
  selectedReferenceTemplateId: string | null;
  selectedReferenceTemplateTitle: string | null;
  generationJob: GenerationJob;
  currentQuestion: OptionQuestion | null;
  conversationMessages: ChatFlowState["conversationMessages"];
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    const normalized = stringValue(value);
    if (normalized) {
      return normalized;
    }
  }
  return "";
}

function copyMode(value: unknown): CopyGenerationMode {
  const mode = stringValue(value);
  if (mode === "suggest_candidates" || mode === "auto_pilot" || mode === "custom_input" || mode === "no_copy") {
    return mode;
  }
  return "suggest_candidates";
}

function imageEngine(value: unknown): ImageGenerationEngine {
  const engine = stringValue(value);
  if (engine === "gpt_image_1" || engine === "gpt_image_2" || engine === "flux2_klein_4b" || engine === "sd35_large") {
    return engine;
  }
  if (engine === "flux" || engine === "flux_schnell" || engine === "flux_1_schnell" || engine === "flux2_klein") {
    return "flux2_klein_4b";
  }
  return DEFAULT_IMAGE_GENERATION_ENGINE;
}

function snapshotStatus(snapshotKind: string, payload: Record<string, unknown>, currentQuestion: OptionQuestion | null): string {
  if (snapshotKind === "waiting_user_input" || currentQuestion) {
    return "waiting_user_input";
  }
  if (snapshotKind === "job_completed" || asRecord(payload.result_payload).status === "done") {
    return "done";
  }
  if (snapshotKind === "job_failed") {
    return "failed";
  }
  return "queued";
}

function copyCandidatesFrom(value: unknown): CopyOption[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const candidates: CopyOption[] = [];
  value.forEach((candidate, index) => {
    const raw = asRecord(candidate);
    const headline = firstString(raw.headline, raw.title, raw.copy);
    if (!headline) {
      return;
    }
    candidates.push({
      id: firstString(raw.id) || `copy_${index + 1}`,
      headline,
      subcopy: firstString(raw.subcopy, raw.body) || null,
      cta: firstString(raw.cta) || null
    });
  });
  return candidates;
}

function copyCandidateOrigin(value: unknown): CopyCandidateOrigin {
  const origin = stringValue(value);
  return origin === "llm" || origin === "rule_based" || origin === "fallback" || origin === "unknown" ? origin : "unknown";
}

const contextDisplayLabels: Record<string, string> = {
  beauty_nail: "네일샵",
  beauty_salon: "뷰티/미용실",
  cafe: "카페",
  restaurant: "음식점/식당",
  store: "일반 매장/소매",
  seasonal_limited: "시즌 한정 홍보",
  discount_event: "할인 이벤트",
  new_launch: "신메뉴/신상품 출시",
  reservation_cta: "예약/방문 유도",
  brand_awareness: "브랜드 인지도",
  review_event: "리뷰 이벤트",
  retention: "재방문 유도"
};

function contextValue(...values: unknown[]): string {
  const value = firstString(...values);
  return contextDisplayLabels[value] ?? value;
}

function optionQuestionFrom(value: unknown): OptionQuestion | null {
  const question = asRecord(value);
  const field = stringValue(question.field);
  const text = stringValue(question.question);
  const options = Array.isArray(question.options) ? question.options : [];
  if (!field || !text) {
    return null;
  }
  return {
    field,
    question: text,
    options: options as OptionQuestion["options"],
    required: typeof question.required === "boolean" ? question.required : undefined,
    multi_select: typeof question.multi_select === "boolean" ? question.multi_select : undefined
  };
}

function extractQuestion(payload: Record<string, unknown>, metadata: Record<string, unknown>): OptionQuestion | null {
  const payloadInterrupt = asRecord(payload.pending_interrupt);
  const metadataInterrupt = asRecord(metadata.pending_interrupt);
  return (
    optionQuestionFrom(payload.option_question) ??
    optionQuestionFrom(payload.question) ??
    optionQuestionFrom(payloadInterrupt.option_question) ??
    optionQuestionFrom(metadataInterrupt.option_question)
  );
}

function failedJobErrorFrom(metadata: Record<string, unknown>): Record<string, string | null> | undefined {
  const errorCode = firstString(metadata.error_code, metadata.errorCode);
  const message = firstString(metadata.message, metadata.error_message, metadata.errorMessage);
  const detail = firstString(metadata.detail, metadata.error_detail, metadata.errorDetail);
  if (!errorCode && !message && !detail) {
    return undefined;
  }
  return {
    error_code: errorCode || null,
    message: message || null,
    detail: detail || null
  };
}

export function mapChatThreadSnapshotToRestoreState(snapshot: ChatStateSnapshotResponse | null | undefined): ThreadSnapshotRestoreState | null {
  if (!snapshot) {
    return null;
  }

  const payload = asRecord(snapshot.state_payload);
  const metadata = asRecord(snapshot.metadata);
  const payloadContext = asRecord(payload.context);
  const metadataContext = asRecord(metadata.context);
  const currentBrief = asRecord(payload.current_brief);
  const prompt = firstString(payload.user_input, payload.prompt, metadata.user_input_preview);
  const threadId = firstString(snapshot.thread_id, payload.thread_id);
  const jobId = firstString(snapshot.job_id, payload.job_id);
  if (!threadId) {
    return null;
  }

  const currentQuestion = extractQuestion(payload, metadata);
  const resultPayload = asRecord(payload.result_payload);
  const progressState = asRecord(payload.progress_state);
  const copyCandidates = copyCandidatesFrom(payload.copy_candidates ?? payload.copyCandidates);
  const status = snapshotStatus(snapshot.snapshot_kind, payload, currentQuestion);
  const context = {
    businessType: contextValue(
      payloadContext.business_type,
      payloadContext.businessType,
      metadataContext.business_type,
      metadataContext.businessType,
      payload.business_type,
      payload.businessType,
      currentBrief.business_type,
      currentBrief.businessType
    ),
    itemOrService: contextValue(
      payloadContext.item_or_service,
      payloadContext.itemOrService,
      metadataContext.item_or_service,
      metadataContext.itemOrService,
      payload.item_or_service,
      payload.itemOrService,
      currentBrief.item_or_service,
      currentBrief.itemOrService
    ),
    promotionGoal: contextValue(
      payloadContext.promotion_goal,
      payloadContext.promotionGoal,
      metadataContext.promotion_goal,
      metadataContext.promotionGoal,
      payload.promotion_goal,
      payload.promotionGoal,
      currentBrief.promotion_goal,
      currentBrief.promotionGoal
    )
  };

  const conversationMessages: ChatFlowState["conversationMessages"] = [];
  if (prompt) {
    conversationMessages.push({ role: "user", text: prompt });
  }
  if (currentQuestion) {
    conversationMessages.push({ role: "assistant", text: currentQuestion.question });
  }

  const restoredGenerationJob: GenerationJob = {
    job_id: jobId,
    thread_id: threadId,
    status,
    progress: {
      progress_percent: Number(progressState.progress_percent ?? progressState.progressPercent ?? (status === "done" ? 100 : 0)),
      current_stage: firstString(progressState.current_stage, progressState.currentStage) || (status === "done" ? "completed" : status),
      message: firstString(progressState.message) || null
    },
    result_payload: Object.keys(resultPayload).length > 0 ? resultPayload : null,
    metadata: currentQuestion ? { pending_interrupt: { type: "option_question", option_question: currentQuestion } } : {}
  };
  const failedError = status === "failed" ? failedJobErrorFrom(metadata) : undefined;
  if (failedError) {
    restoredGenerationJob.error = failedError;
  }

  return {
    prompt,
    jobId,
    threadId,
    context,
    copyGenerationMode: copyMode(payload.copy_generation_mode ?? payload.copyGenerationMode),
    copyCandidates,
    copyCandidateOrigin: copyCandidateOrigin(payload.copy_candidate_origin ?? payload.copyCandidateOrigin),
    selectedCopyId: firstString(payload.selected_copy_id, payload.selectedCopyId, copyCandidates[0]?.id),
    selectedChannelId: firstString(payload.selected_channel_id, payload.selectedChannelId, payload.ad_format) || "instagram-feed",
    selectedTone: firstString(payload.selected_tone, payload.selectedTone) || "감성적인",
    selectedImageGenerationEngine: imageEngine(
      payload.image_generation_engine ??
        payload.imageGenerationEngine ??
        payload.selected_image_generation_engine ??
        payload.selectedImageGenerationEngine ??
        payload.engine ??
        currentBrief.requested_engine ??
        currentBrief.requestedEngine ??
        currentBrief.engine ??
        resultPayload.engine ??
        resultPayload.requested_engine ??
        resultPayload.requestedEngine ??
        metadata.requested_engine ??
        metadata.requestedEngine ??
        metadata.t2i_engine ??
        metadata.t2iEngine ??
        metadata.selected_engine ??
        metadata.selectedEngine ??
        metadata.engine
    ),
    customDirection: firstString(payload.custom_direction, payload.customDirection),
    userCustomHeadline: firstString(payload.user_custom_headline, payload.userCustomHeadline, currentBrief.user_custom_headline),
    userCustomSubcopy: firstString(payload.user_custom_subcopy, payload.userCustomSubcopy, currentBrief.user_custom_subcopy),
    sourceAssetId: firstString(payload.source_asset_id, payload.sourceAssetId, currentBrief.source_asset_id, currentBrief.sourceAssetId) || null,
    sourceImagePath: firstString(payload.source_image_path, payload.sourceImagePath) || null,
    referenceImagePath: firstString(payload.reference_image_path, payload.referenceImagePath) || null,
    selectedReferenceTemplateId:
      firstString(snapshot.selected_reference_template_id, payload.selected_reference_template_id, payload.selectedReferenceTemplateId) || null,
    selectedReferenceTemplateTitle:
      firstString(asRecord(snapshot.reference_template_snapshot).title, payload.selected_reference_template_title, payload.selectedReferenceTemplateTitle) ||
      null,
    generationJob: restoredGenerationJob,
    currentQuestion,
    conversationMessages
  };
}

function messageContent(message: ChatMessageResponse): string {
  const content = stringValue(message.content);
  if (content === "Waiting for user input.") {
    return "";
  }
  const briefMarkerIndex = content.indexOf("[광고 브리프]");
  if (briefMarkerIndex > -1) {
    return content.slice(0, briefMarkerIndex).trim();
  }
  if (content) {
    return content;
  }
  const payload = asRecord(message.payload);
  return firstString(payload.display_text, payload.displayText, payload.label, payload.text, payload.question);
}

export function mapChatMessagesToTranscript(messages: ChatMessageResponse[]): ChatFlowState["conversationMessages"] {
  return [...messages]
    .sort((a, b) => a.sequence_no - b.sequence_no)
    .flatMap((message) => {
      if (message.role !== "user" && message.role !== "assistant") {
        return [];
      }
      const text = messageContent(message);
      if (!text) {
        return [];
      }
      return [{ role: message.role, text }];
    });
}
