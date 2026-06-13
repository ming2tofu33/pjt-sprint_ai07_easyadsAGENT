"use client";

import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatHistoryStep } from "@/components/generate/ChatHistoryStep";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatAnalysisPendingStep } from "@/components/generate/ChatAnalysisPendingStep";
import { ChatContextQuestionStep } from "@/components/generate/ChatContextQuestionStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { DashboardToast } from "@/components/generate/DashboardToast";
import { GenerationCompleteStep } from "@/components/generate/GenerationCompleteStep";
import { GenerationInProgressStep } from "@/components/generate/GenerationInProgressStep";
import { GenerationJobInterruptStep } from "@/components/generate/GenerationJobInterruptStep";
import { HomeStartStep } from "@/components/generate/HomeStartStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { MyPageStep } from "@/components/generate/MyPageStep";
import { PhotoGenerateStep } from "@/components/generate/PhotoGenerateStep";
import { RecentAdsStep } from "@/components/generate/RecentAdsStep";
import { ReferenceBrowseStep } from "@/components/generate/ReferenceBrowseStep";
import { StudioEntryStep } from "@/components/generate/StudioEntryStep";
import { ThreadLimitModal } from "@/components/generate/ThreadLimitModal";
import {
  answerGenerationJob,
  answerChatQuestion,
  archiveChatThread,
  createChatBrief,
  createGenerationJob,
  deleteArchiveItem,
  getChatThreadMessages,
  getChatThreadState,
  getGenerationJob,
  listArchiveItems,
  saveArchiveItem,
  startPhotoGeneration,
  updateArchiveItem,
  uploadPhotoAsset,
  uploadReferenceAsset,
  ApiError,
  type ChatTurnResponse,
  type GenerationJob,
  type GenerationStartOptions,
  type ReferenceTemplateCard
} from "@/lib/api-client";
import { buildAdHref } from "@/lib/ad-navigation";
import { archiveItemToCreative } from "@/lib/archive-creative";
import {
  clearChatFlowSnapshot,
  clearChatTurnSnapshot,
  clearGenerationFailureSnapshot,
  readChatFlowBackTarget,
  readChatFlowSnapshot,
  readChatTurnSnapshot,
  readGenerationFailureSnapshot,
  writeChatFlowBackTarget,
  writeChatFlowSnapshot,
  writeChatTurnSnapshot,
  writeGenerationFailureSnapshot,
  type ChatFlowSnapshot,
  type ChatTurnSnapshot
} from "@/lib/chat-snapshots";
import { mapChatMessagesToTranscript, mapChatThreadSnapshotToRestoreState } from "@/lib/chat-thread-state-mapper";
import { buildBrief, chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";
import {
  buildDashboardHref,
  type DashboardStage,
  type DashboardSurface
} from "@/lib/dashboard-navigation";
import {
  addGeneratedCreativeSnapshot,
  readGeneratedCreatives,
  removeGeneratedCreative
} from "@/lib/generated-creative-storage";
import { getPendingGenerationJobParsedInterrupt } from "@/lib/generation-job-interrupt";
import {
  DEFAULT_IMAGE_GENERATION_ENGINE,
  getGenerationEngineOption,
  isTerminalGenerationJobStatus,
  resolveGenerationEnginePreference,
  resolveGenerationRunMode,
  type ImageGenerationEngine
} from "@/lib/generation-engine";
import {
  appendSavedBrandKitContext,
  clearGenerationDraftPrompt,
  consumeFreshGenerationRequest,
  readGenerationDraftReferenceTemplateId,
  readGenerationRequestContext,
  saveGenerationRequestContext,
  writeGenerationDraftPrompt,
  writeGenerationDraftReferenceTemplateId
} from "@/lib/generation-request-context";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { buildReferenceStyleHref } from "@/lib/reference-navigation";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import type {
  ChatBrief,
  ChatFlowState,
  CopyCandidateOrigin,
  CopyGenerationMode,
  InferredContext,
  OptionQuestion,
  PartialInferredContext
} from "@/types/marketing";
import styles from "@/components/generate/generate.module.css";
import { useChatRouteRestore } from "./useChatRouteRestore";

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing" | "jobQuestion";
type ArchiveLoadState = "idle" | "loading" | "ready" | "error";

type ChatGenerateClientProps = {
  initialSurface?: DashboardSurface;
  initialStage?: DashboardStage;
};

const ARCHIVE_CREATIVES_CACHE_STORAGE_KEY = "easyads_archive_creatives_cache_v1";
const ARCHIVE_CREATIVES_CACHE_LIMIT = 20;
const GENERATION_JOB_POLL_INTERVAL_MS = 1800;
const GENERATION_JOB_MAX_POLLS = 80;
const ignoreRouteJobRestore = (_jobId: string) => {};
const ignoreRouteThreadRestore = (_threadId: string) => {};
const AD_FORMAT_BY_CHANNEL_ID: Record<string, string> = {
  "instagram-feed": "instagram_feed",
  "instagram-story": "instagram_story",
  poster: "poster",
  flyer: "flyer"
};

function mergeBriefRefinement(existingDirection: string, refinement: string): string {
  return [existingDirection.trim(), refinement.trim()].filter(Boolean).join("\n");
}

type ArchiveCreativesCache = {
  cachedAt: string;
  creatives: MockCreative[];
};

function isCachedCreative(value: unknown): value is MockCreative {
  if (!value || typeof value !== "object") {
    return false;
  }
  const creative = value as { id?: unknown; title?: unknown };
  return typeof creative.id === "string" && typeof creative.title === "string";
}

function mergeArchiveCreatives(...creativeGroups: MockCreative[][]): MockCreative[] {
  const seen = new Set<string>();
  return creativeGroups
    .flat()
    .filter((creative) => {
      if (seen.has(creative.id)) {
        return false;
      }
      seen.add(creative.id);
      return true;
    });
}

function readArchiveCreativesCache(): MockCreative[] {
  try {
    const raw = window.localStorage.getItem(ARCHIVE_CREATIVES_CACHE_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as Partial<ArchiveCreativesCache>;
    return Array.isArray(parsed.creatives)
      ? parsed.creatives.filter(isCachedCreative).slice(0, ARCHIVE_CREATIVES_CACHE_LIMIT)
      : [];
  } catch {
    return [];
  }
}

function writeArchiveCreativesCache(creatives: MockCreative[]) {
  try {
    window.localStorage.setItem(
      ARCHIVE_CREATIVES_CACHE_STORAGE_KEY,
      JSON.stringify({
        cachedAt: new Date().toISOString(),
        creatives: mergeArchiveCreatives(creatives).slice(0, ARCHIVE_CREATIVES_CACHE_LIMIT)
      })
    );
  } catch {
    // The archive can still render from memory if browser storage is unavailable.
  }
}

function updateArchiveCreativesCache(updater: (current: MockCreative[]) => MockCreative[]) {
  writeArchiveCreativesCache(updater(readArchiveCreativesCache()));
}

function upsertArchiveCreativeCacheItem(creative: MockCreative) {
  updateArchiveCreativesCache((current) => mergeArchiveCreatives([creative], current));
}

function removeArchiveCreativeCacheItem(creativeId: string) {
  updateArchiveCreativesCache((current) => current.filter((creative) => creative.id !== creativeId));
}

function isQuestionResponse(response: ChatTurnResponse): response is Extract<ChatTurnResponse, { type: "option_question" }> {
  return response.type === "option_question";
}

function isBriefReadyResponse(response: ChatTurnResponse): response is Extract<ChatTurnResponse, { type: "brief_ready" }> {
  return response.type === "brief_ready";
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function toCanonicalAdFormat(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return AD_FORMAT_BY_CHANNEL_ID[value] ?? value;
}

function buildGenerationJobUserInput(state: ChatFlowState) {
  return state.userInput;
}

function buildGenerationJobBriefMetadata(state: ChatFlowState) {
  const brief = buildBrief(state);
  const isDeferredCopySelection = state.copyGenerationMode === "suggest_candidates";
  return {
    purpose: brief.purpose,
    item: brief.item,
    copy: isDeferredCopySelection ? null : brief.copy,
    copy_status: isDeferredCopySelection ? "pending_graph_interrupt" : "resolved",
    tone: brief.tone,
    channel: brief.channel,
    image_direction: brief.imageDirection
  };
}

function buildDeferredCopyBrief(state: ChatFlowState, customDirection = state.customDirection): ChatBrief {
  return buildBrief({
    ...state,
    brief: null,
    selectedCopyId: "",
    customDirection
  });
}

function toGenerationJobThreadId(threadId: string | null | undefined): string | undefined {
  const normalized = threadId?.trim();
  return normalized?.startsWith("thread_") ? normalized : undefined;
}

function buildChatStageHrefWithJob(stage: DashboardStage, params: { jobId?: string | null; threadId?: string | null } = {}) {
  const baseHref = buildDashboardHref("chat", stage);
  const query = new URLSearchParams();
  if (params.jobId) {
    query.set("jobId", params.jobId);
  }
  const threadId = toGenerationJobThreadId(params.threadId);
  if (threadId) {
    query.set("threadId", threadId);
  }
  const queryString = query.toString();
  return queryString ? `${baseHref}?${queryString}` : baseHref;
}

function buildChatStageHrefForJob(stage: DashboardStage, job: GenerationJob) {
  return buildChatStageHrefWithJob(stage, {
    jobId: job.job_id,
    threadId: job.thread_id
  });
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function isFinalImageGenerationJob(job: GenerationJob | null | undefined): boolean {
  const metadata = asRecord(job?.metadata);
  const finalBrief = asRecord(metadata.final_brief ?? metadata.finalBrief);
  return metadata.source === "web_generation_flow" || Object.keys(finalBrief).length > 0;
}

function getPayloadArray<T = unknown>(payload: Record<string, unknown>, ...keys: string[]): T[] {
  for (const key of keys) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value as T[];
    }
  }
  return [];
}

function getPayloadString(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return null;
}

function getCopyCandidateOrigin(payload: Record<string, unknown>, ...keys: string[]): CopyCandidateOrigin {
  const value = getPayloadString(payload, ...keys);
  return value === "llm" || value === "rule_based" || value === "fallback" || value === "unknown" ? value : "unknown";
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

function displayContextValue(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return contextDisplayLabels[value] ?? value;
}

function normalizePartialContext(context: Record<string, unknown>): PartialInferredContext {
  return {
    businessType: displayContextValue(getPayloadString(context, "businessType", "business_type")),
    itemOrService: displayContextValue(getPayloadString(context, "itemOrService", "item_or_service")),
    promotionGoal: displayContextValue(getPayloadString(context, "promotionGoal", "promotion_goal"))
  };
}

function normalizeInferredContext(context: Record<string, unknown>): InferredContext {
  return {
    businessType: displayContextValue(getPayloadString(context, "businessType", "business_type")) ?? "",
    itemOrService: displayContextValue(getPayloadString(context, "itemOrService", "item_or_service")) ?? "",
    promotionGoal: displayContextValue(getPayloadString(context, "promotionGoal", "promotion_goal")) ?? ""
  };
}

function extractGenerationJobContext(payload: Record<string, unknown>, metadata: Record<string, unknown>): Record<string, unknown> {
  const payloadContext = asRecord(payload.context);
  const payloadInferredContext = asRecord(payload.inferred_context);
  const metadataContext = asRecord(metadata.context);
  const payloadBrief = asRecord(payload.current_brief ?? payload.brief ?? payload.final_brief);
  const metadataBrief = asRecord(metadata.current_brief ?? metadata.brief ?? metadata.final_brief);

  return {
    ...metadata,
    ...payload,
    ...metadataBrief,
    ...payloadBrief,
    ...metadataContext,
    ...payloadInferredContext,
    ...payloadContext
  };
}

function normalizeChatBrief(
  brief: Record<string, unknown>,
  context: InferredContext,
  payload: Record<string, unknown>
): ChatBrief {
  const copy =
    getPayloadString(brief, "copy", "copy_text", "headline", "user_custom_headline") ??
    getPayloadString(payload, "copy", "copy_text", "headline", "user_custom_headline") ??
    "";
  const imageDirection =
    getPayloadString(brief, "imageDirection", "image_direction", "prompt_text", "visual_direction") ??
    getPayloadString(payload, "imageDirection", "image_direction", "prompt_text", "visual_direction") ??
    "";
  const finalImagePath = getPayloadString(brief, "finalImagePath", "final_image_path") ?? getPayloadString(payload, "finalImagePath", "final_image_path");

  return {
    purpose: getPayloadString(brief, "purpose", "promotion_goal") ?? context.promotionGoal,
    item: getPayloadString(brief, "item", "item_or_service") ?? context.itemOrService,
    copy,
    tone: getPayloadString(brief, "tone", "brand_tone", "selected_tone") ?? "",
    channel: getPayloadString(brief, "channel", "selected_channel_id", "requested_ad_format") ?? "",
    imageDirection,
    finalImagePath
  };
}

function fallbackQuestionForMissingFields(missingFields: string[]): OptionQuestion {
  const field = missingFields[0] ?? "custom_request";
  const fallbackQuestions: Record<string, OptionQuestion> = {
    business_type: {
      field: "business_type",
      question: "어떤 업종의 광고인가요?",
      options: [
        { id: 1, label: "음식점/식당", value: "restaurant" },
        { id: 2, label: "카페/디저트", value: "cafe" },
        { id: 3, label: "뷰티/미용실", value: "beauty_salon" },
        { id: 4, label: "직접 입력", value: "custom" }
      ]
    },
    item_or_service: {
      field: "item_or_service",
      question: "홍보할 상품이나 서비스는 무엇인가요?",
      options: [
        { id: 1, label: "대표 메뉴", value: "signature_item" },
        { id: 2, label: "신상품", value: "new_item" },
        { id: 3, label: "예약 서비스", value: "reservation_service" },
        { id: 4, label: "직접 입력", value: "custom" }
      ]
    },
    promotion_goal: {
      field: "promotion_goal",
      question: "어떤 목적의 광고를 만들까요?",
      options: [
        { id: 1, label: "신메뉴/신상품 출시", value: "new_launch" },
        { id: 2, label: "시즌 한정 홍보", value: "seasonal_limited" },
        { id: 3, label: "할인 이벤트", value: "discount_event" },
        { id: 4, label: "예약/방문 유도", value: "reservation_cta" },
        { id: 5, label: "직접 입력", value: "custom" }
      ]
    },
    ad_format: {
      field: "ad_format",
      question: "어디에 사용할 광고인가요?",
      options: [
        { id: 1, label: "인스타그램 피드 1:1", value: "instagram_feed" },
        { id: 2, label: "인스타그램 스토리 9:16", value: "instagram_story" },
        { id: 3, label: "포스터 4:5", value: "poster" },
        { id: 4, label: "전단지 A4", value: "flyer" }
      ]
    },
    copy_generation_mode: {
      field: "copy_generation_mode",
      question: "광고에 들어갈 홍보 문구는 어떻게 준비할까요?",
      options: [
        { id: 1, label: "AI에게 문구 추천 받기", value: "suggest_candidates" },
        { id: 2, label: "AI가 한 문구로 자동 완성", value: "auto_pilot" },
        { id: 3, label: "이미지만 생성", value: "no_copy" },
        { id: 4, label: "직접 문구 입력", value: "custom_input" }
      ]
    },
    custom_request: {
      field: "custom_request",
      question: "추가로 반영할 요청이 있나요?",
      options: [
        { id: 1, label: "있음", value: "include_custom_request" },
        { id: 2, label: "없음", value: "none" }
      ]
    }
  };
  return fallbackQuestions[field] ?? fallbackQuestions.custom_request;
}

function generationJobToChatTurnResponse(job: GenerationJob, fallbackCopyGenerationMode?: CopyGenerationMode): ChatTurnResponse {
  const payload = asRecord(job.result_payload);
  const metadata = asRecord(job.metadata);
  const context = extractGenerationJobContext(payload, metadata);
  const threadId = job.thread_id ?? `thread_${job.job_id}`;

  if (job.status === "waiting_user_input") {
    const interrupt = getPendingGenerationJobParsedInterrupt(job);
    if (interrupt?.type === "copy_candidate_selection") {
      return {
        type: "copy_candidates",
        jobId: job.job_id,
        threadId,
        status: job.status,
        context: normalizeInferredContext(context),
        copyCandidates: interrupt.candidates as never[],
        recommendedCopyId: interrupt.recommendedCandidateId ?? null,
        copyCandidateOrigin: interrupt.copyCandidateOrigin,
        copyGenerationMode: fallbackCopyGenerationMode ?? "suggest_candidates"
      };
    }
    if (interrupt?.type === "option_question") {
      return {
        type: "option_question",
        jobId: job.job_id,
        threadId,
        status: "waiting",
        context: normalizePartialContext(context),
        question: interrupt.optionQuestion as never,
        missingFields: getPayloadArray<string>(metadata, "missingFields", "missing_fields"),
        generationJob: job
      };
    }
    const pendingInterrupt = asRecord(metadata.pending_interrupt);
    const missingFields =
      getPayloadArray<string>(payload, "missingFields", "missing_fields").length > 0
        ? getPayloadArray<string>(payload, "missingFields", "missing_fields")
        : getPayloadArray<string>(metadata, "missingFields", "missing_fields");
    const question =
      payload.question ??
      payload.option_question ??
      pendingInterrupt.option_question ??
      fallbackQuestionForMissingFields(missingFields);

    return {
      type: "option_question",
      jobId: job.job_id,
      threadId,
      status: "waiting",
      context: normalizePartialContext(context),
      question: question as never,
      missingFields,
      generationJob: job
    };
  }

  const normalizedContext = normalizeInferredContext(context);
  const copyCandidates = getPayloadArray(payload, "copyCandidates", "copy_candidates");
  if (copyCandidates.length > 0 || payload.type === "copy_candidates") {
    return {
      type: "copy_candidates",
      jobId: job.job_id,
      threadId,
      status: job.status,
      context: normalizedContext,
      copyCandidates: copyCandidates as never[],
      recommendedCopyId: getPayloadString(payload, "recommendedCopyId", "recommended_copy_id"),
      copyCandidateOrigin: getCopyCandidateOrigin(payload, "copyCandidateOrigin", "copy_candidate_origin"),
      copyGenerationMode: fallbackCopyGenerationMode
    };
  }

  const brief = asRecord(payload.brief ?? payload.final_brief ?? payload.current_brief ?? metadata.brief ?? metadata.final_brief ?? metadata.current_brief);

  return {
    type: "brief_ready",
    jobId: job.job_id,
    threadId,
    status: job.status,
    context: normalizedContext,
    brief: normalizeChatBrief(brief, normalizedContext, payload),
    copyGenerationMode: fallbackCopyGenerationMode ?? "no_copy"
  };
}

function shouldPollInitialGenerationJob(job: GenerationJob): boolean {
  return job.status !== "waiting_user_input" && !isTerminalGenerationJobStatus(job.status);
}

function mergeContextFromTurnResponse(
  baseContext: InferredContext,
  response: ChatTurnResponse
): InferredContext {
  return {
    businessType: response.context.businessType || baseContext.businessType,
    itemOrService: response.context.itemOrService || baseContext.itemOrService,
    promotionGoal: response.context.promotionGoal || baseContext.promotionGoal
  };
}

type PhotoGenerateInput = {
  file: File;
  prompt: string;
} & GenerationStartOptions;

type InitialChatIntakeContext = {
  prompt: string;
  copyGenerationMode?: CopyGenerationMode;
  imageGenerationEngine: ImageGenerationEngine;
  sourceImagePath?: string | null;
  referenceImagePath?: string | null;
  selectedReferenceTemplateId?: string | null;
  selectedReferenceTemplateTitle?: string | null;
  userCustomHeadline?: string | null;
  userCustomSubcopy?: string | null;
};

function chatTurnSnapshotThreadId(snapshot: ChatTurnSnapshot): string | null {
  return snapshot.generationJob?.thread_id ?? snapshot.response?.threadId ?? null;
}

function chatTurnSnapshotMatchesThread(snapshot: ChatTurnSnapshot | null, threadId: string | null | undefined): snapshot is ChatTurnSnapshot {
  if (!snapshot) {
    return false;
  }
  if (!threadId) {
    return true;
  }
  const snapshotThreadId = chatTurnSnapshotThreadId(snapshot);
  return !snapshotThreadId || snapshotThreadId === threadId;
}

function initialChatIntakeFromTurnSnapshot(snapshot: ChatTurnSnapshot): InitialChatIntakeContext {
  return {
    prompt: snapshot.prompt,
    copyGenerationMode: snapshot.copyGenerationMode,
    imageGenerationEngine: snapshot.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
    sourceImagePath: snapshot.sourceImagePath ?? null,
    referenceImagePath: snapshot.referenceImagePath ?? null,
    selectedReferenceTemplateId: snapshot.selectedReferenceTemplateId ?? null,
    selectedReferenceTemplateTitle: snapshot.selectedReferenceTemplateTitle ?? null,
    userCustomHeadline: snapshot.userCustomHeadline ?? null,
    userCustomSubcopy: snapshot.userCustomSubcopy ?? null
  };
}

function applyReferenceTemplateFromTurnSnapshot(state: ChatFlowState, snapshot: ChatTurnSnapshot): ChatFlowState {
  if (!snapshot.selectedReferenceTemplateId) {
    return state;
  }
  return chatFlowReducer(state, {
    type: "referenceTemplateSelected",
    selectedReferenceTemplateId: snapshot.selectedReferenceTemplateId,
    selectedReferenceTemplateTitle: snapshot.selectedReferenceTemplateTitle ?? null
  });
}

function createChatFlowStateFromTurnSnapshot(snapshot: ChatTurnSnapshot): ChatFlowState {
  let nextState = chatFlowReducer(createInitialChatFlowState(), {
    type: "submitPrompt",
    prompt: snapshot.prompt,
    copyGenerationMode: snapshot.copyGenerationMode,
    imageGenerationEngine: snapshot.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
    sourceImagePath: snapshot.sourceImagePath ?? null,
    referenceImagePath: snapshot.referenceImagePath ?? null,
    userCustomHeadline: snapshot.userCustomHeadline ?? null,
    userCustomSubcopy: snapshot.userCustomSubcopy ?? null
  });

  nextState = applyReferenceTemplateFromTurnSnapshot(nextState, snapshot);

  if (snapshot.generationJob && !snapshot.response) {
    return chatFlowReducer(nextState, {
      type: "generationJobUpdated",
      generationJob: snapshot.generationJob
    });
  }

  if (!snapshot.response) {
    return nextState;
  }

  if (isQuestionResponse(snapshot.response)) {
    return chatFlowReducer(nextState, {
      type: "backendQuestionReceived",
      jobId: snapshot.response.jobId,
      threadId: snapshot.response.threadId,
      context: snapshot.response.context,
      question: snapshot.response.question,
      generationJob: snapshot.response.generationJob,
      sourceImagePath: snapshot.sourceImagePath ?? null,
      referenceImagePath: snapshot.referenceImagePath ?? null
    });
  }

  if (isBriefReadyResponse(snapshot.response)) {
    nextState = chatFlowReducer(nextState, {
      type: "backendStartSucceeded",
      prompt: snapshot.prompt,
      jobId: snapshot.response.jobId,
      threadId: snapshot.response.threadId,
      context: snapshot.response.context,
      copyCandidates: [],
      recommendedCopyId: null,
      copyCandidateSource: "empty",
      copyCandidateOrigin: "unknown",
      copyGenerationMode: snapshot.response.copyGenerationMode,
      imageGenerationEngine: snapshot.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
      sourceImagePath: snapshot.sourceImagePath ?? null,
      referenceImagePath: snapshot.referenceImagePath ?? null,
      userCustomHeadline: snapshot.userCustomHeadline ?? null,
      userCustomSubcopy: snapshot.userCustomSubcopy ?? null
    });
    nextState = chatFlowReducer(nextState, { type: "backendBriefSucceeded", brief: snapshot.response.brief });
    return chatFlowReducer(nextState, { type: "continueToBrief" });
  }

  return chatFlowReducer(nextState, {
    type: "backendStartSucceeded",
    prompt: snapshot.prompt,
    jobId: snapshot.response.jobId,
    threadId: snapshot.response.threadId,
    context: snapshot.response.context,
    copyCandidates: snapshot.response.copyCandidates,
    recommendedCopyId: snapshot.response.recommendedCopyId,
    copyCandidateOrigin: snapshot.response.copyCandidateOrigin,
    copyGenerationMode: snapshot.response.copyGenerationMode,
    imageGenerationEngine: snapshot.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
    sourceImagePath: snapshot.sourceImagePath ?? null,
    referenceImagePath: snapshot.referenceImagePath ?? null,
    userCustomHeadline: snapshot.userCustomHeadline ?? null,
    userCustomSubcopy: snapshot.userCustomSubcopy ?? null
  });
}

function createInitialChatFlowStateForRoute(input: {
  initialSurface: DashboardSurface;
  initialStage: DashboardStage;
  threadId?: string | null;
}): ChatFlowState {
  if (input.initialSurface !== "chat" || input.initialStage !== "start") {
    return createInitialChatFlowState();
  }

  const pendingTurn = readChatTurnSnapshot();
  if (!chatTurnSnapshotMatchesThread(pendingTurn, input.threadId)) {
    return createInitialChatFlowState();
  }

  return createChatFlowStateFromTurnSnapshot(pendingTurn);
}

export function ChatGenerateClient({ initialSurface = "home", initialStage = "start" }: ChatGenerateClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobIdParam = searchParams?.get("jobId");
  const threadIdParam = searchParams?.get("threadId");
  const [state, dispatch] = useReducer(
    chatFlowReducer,
    { initialSurface, initialStage, threadId: threadIdParam },
    createInitialChatFlowStateForRoute
  );
  const [optimisticSurface, setOptimisticSurface] = useState<DashboardSurface | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [generatedCreatives, setGeneratedCreatives] = useState<MockCreative[]>([]);
  const [archiveLoadState, setArchiveLoadState] = useState<ArchiveLoadState>("idle");
  const [archiveReloadToken, setArchiveReloadToken] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
  const [isCurrentThreadDeleteOpen, setCurrentThreadDeleteOpen] = useState(false);
  const [isDeletingCurrentThread, setDeletingCurrentThread] = useState(false);
  const [currentThreadDeleteError, setCurrentThreadDeleteError] = useState<string | null>(null);
  const activeThreadRef = useRef({ threadId: "", conversationMessageCount: 0 });
  const finalGenerationJobIdsRef = useRef<Set<string>>(new Set());
  const appSurface = optimisticSurface ?? initialSurface;
  const prepareMissingGeneratingRoute = useCallback(() => {
    dispatch({ type: "reset" });
    dispatch({ type: "showResultShell" });
  }, []);
  const lastPrimedStageRef = useChatRouteRestore({
    appSurface,
    initialStage,
    jobIdParam,
    threadIdParam,
    setGenerationStage,
    restoreJob: ignoreRouteJobRestore,
    restoreThread: ignoreRouteThreadRestore,
    prepareMissingGeneratingRoute
  });
  const currentGenerationJobInterrupt = getPendingGenerationJobParsedInterrupt(state.generationJob);

  function isClientFinalImageGenerationJob(job: GenerationJob | null | undefined): boolean {
    return isFinalImageGenerationJob(job) || (Boolean(job?.job_id) && finalGenerationJobIdsRef.current.has(job?.job_id ?? ""));
  }

  const showArchiveStoragePendingToast = useCallback((title: string) => {
    showToast(`${title} 저장은 실제 보관함 연결 후 사용할 수 있어요.`);
  }, []);

  const navigateTo = useCallback(
    (surface: DashboardSurface, stage?: DashboardStage) => {
      if (surface === "chat" || surface === "photo") {
        writeChatFlowBackTarget(appSurface);
      }
      setOptimisticSurface(surface);
      router.push(buildDashboardHref(surface, stage));
    },
    [appSurface, router]
  );

  const restoreBriefSnapshot = useCallback((snapshot: ChatFlowSnapshot, stage: DashboardStage) => {
    dispatch({ type: "reset" });
    dispatch({
      type: "backendStartSucceeded",
      prompt: snapshot.prompt,
      jobId: snapshot.jobId,
      threadId: snapshot.threadId,
      context: snapshot.context,
      copyCandidates: snapshot.copyCandidates,
      recommendedCopyId: snapshot.selectedCopyId,
      copyCandidateSource: snapshot.copyCandidateSource,
      copyCandidateOrigin: snapshot.copyCandidateOrigin,
      imageGenerationEngine: snapshot.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
      sourceImagePath: snapshot.sourceImagePath ?? null,
      referenceImagePath: snapshot.referenceImagePath ?? null,
      userCustomHeadline: snapshot.userCustomHeadline ?? null,
      userCustomSubcopy: snapshot.userCustomSubcopy ?? null
    });
    dispatch({ type: "selectTone", tone: snapshot.selectedTone });
    dispatch({ type: "selectCopy", copyId: snapshot.selectedCopyId });
    dispatch({ type: "selectChannel", channelId: snapshot.selectedChannelId });
    dispatch({ type: "setCustomDirection", value: snapshot.customDirection });
    dispatch({ type: "backendBriefSucceeded", brief: snapshot.brief });
    dispatch({ type: "continueToBrief" });
    setGenerationStage(
      stage === "generating" ? "generating" : stage === "similar" ? "similarBrowsing" : stage === "start" ? "brief" : "complete"
    );
    lastPrimedStageRef.current = stage;
  }, []);

  const applyBriefReadyResponse = useCallback(
    (
      prompt: string,
      response: {
        jobId: string;
        threadId: string;
        context: InferredContext;
        brief: ChatBrief;
        copyGenerationMode?: CopyGenerationMode;
        imageGenerationEngine?: ImageGenerationEngine;
        sourceImagePath?: string | null;
        referenceImagePath?: string | null;
        userCustomHeadline?: string | null;
        userCustomSubcopy?: string | null;
      }
    ) => {
      const snapshot = {
        prompt,
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        copyCandidates: [],
        copyCandidateSource: "empty" as const,
        copyCandidateOrigin: "unknown" as const,
        selectedCopyId: "",
        selectedChannelId: "instagram-feed",
        selectedTone: "",
        customDirection: "",
        brief: response.brief,
        imageGenerationEngine: response.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
        sourceImagePath: response.sourceImagePath ?? null,
        referenceImagePath: response.referenceImagePath ?? null,
        userCustomHeadline: response.userCustomHeadline ?? null,
        userCustomSubcopy: response.userCustomSubcopy ?? null
      };
      dispatch({
        type: "backendStartSucceeded",
        prompt,
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        copyCandidates: [],
        recommendedCopyId: null,
        copyCandidateSource: "empty",
        copyCandidateOrigin: "unknown",
        copyGenerationMode: response.copyGenerationMode ?? "no_copy",
        imageGenerationEngine: response.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
        sourceImagePath: response.sourceImagePath ?? null,
        referenceImagePath: response.referenceImagePath ?? null,
        userCustomHeadline: response.userCustomHeadline ?? null,
        userCustomSubcopy: response.userCustomSubcopy ?? null
      });
      dispatch({ type: "backendBriefSucceeded", brief: response.brief });
      dispatch({ type: "continueToBrief" });
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      setGeneratedCreatives(response.brief.finalImagePath ? addGeneratedCreativeSnapshot(snapshot) : readGeneratedCreatives());
      setGenerationStage("brief");
      lastPrimedStageRef.current = "start";
    },
    []
  );

  const applyTurnResponse = useCallback((
    prompt: string,
    response: ChatTurnResponse,
    imageGenerationEngine?: ImageGenerationEngine,
    sourceImagePath?: string | null,
    referenceImagePath?: string | null,
    userCustomHeadline?: string | null,
    userCustomSubcopy?: string | null
  ) => {
    if (isQuestionResponse(response)) {
      dispatch({
        type: "backendQuestionReceived",
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        question: response.question,
        generationJob: response.generationJob,
        sourceImagePath: sourceImagePath ?? null,
        referenceImagePath: referenceImagePath ?? null
      });
      return;
    }
    if (isBriefReadyResponse(response)) {
      applyBriefReadyResponse(prompt, {
        ...response,
        imageGenerationEngine: imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
        sourceImagePath: sourceImagePath ?? null,
        referenceImagePath: referenceImagePath ?? null,
        userCustomHeadline: userCustomHeadline ?? null,
        userCustomSubcopy: userCustomSubcopy ?? null
      });
      return;
    }

    dispatch({
      type: "backendStartSucceeded",
      prompt,
      jobId: response.jobId,
      threadId: response.threadId,
      context: response.context,
      copyCandidates: response.copyCandidates,
      recommendedCopyId: response.recommendedCopyId,
      copyCandidateOrigin: response.copyCandidateOrigin,
      copyGenerationMode: response.copyGenerationMode,
      imageGenerationEngine: imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
      sourceImagePath: sourceImagePath ?? null,
      referenceImagePath: referenceImagePath ?? null,
      userCustomHeadline: userCustomHeadline ?? null,
      userCustomSubcopy: userCustomSubcopy ?? null
    });
  }, [applyBriefReadyResponse]);

  const restoreChatTurnSnapshot = useCallback(
    (pendingTurn: ChatTurnSnapshot) => {
      dispatch({ type: "reset" });
      dispatch({
        type: "submitPrompt",
        prompt: pendingTurn.prompt,
        copyGenerationMode: pendingTurn.copyGenerationMode,
        imageGenerationEngine: pendingTurn.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
        sourceImagePath: pendingTurn.sourceImagePath ?? null,
        referenceImagePath: pendingTurn.referenceImagePath ?? null,
        userCustomHeadline: pendingTurn.userCustomHeadline ?? null,
        userCustomSubcopy: pendingTurn.userCustomSubcopy ?? null
      });
      if (pendingTurn.selectedReferenceTemplateId) {
        dispatch({
          type: "referenceTemplateSelected",
          selectedReferenceTemplateId: pendingTurn.selectedReferenceTemplateId,
          selectedReferenceTemplateTitle: pendingTurn.selectedReferenceTemplateTitle ?? null
        });
      }

      if (pendingTurn.generationJob && !pendingTurn.response) {
        dispatch({ type: "generationJobUpdated", generationJob: pendingTurn.generationJob });
        setGenerationStage("brief");
        lastPrimedStageRef.current = "start";
        setOptimisticSurface("chat");
        void pollGenerationJobUntilDoneOrQuestion(pendingTurn.generationJob, initialChatIntakeFromTurnSnapshot(pendingTurn));
        return;
      }

      if (pendingTurn.response) {
        applyTurnResponse(
          pendingTurn.prompt,
          pendingTurn.response,
          pendingTurn.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
          pendingTurn.sourceImagePath ?? null,
          pendingTurn.referenceImagePath ?? null,
          pendingTurn.userCustomHeadline ?? null,
          pendingTurn.userCustomSubcopy ?? null
        );
        setGenerationStage("brief");
        lastPrimedStageRef.current = "start";
      }
    },
    [applyTurnResponse]
  );

  useEffect(() => {
    setOptimisticSurface(null);
  }, [initialSurface]);

  useEffect(() => {
    activeThreadRef.current = {
      threadId: state.threadId,
      conversationMessageCount: state.conversationMessages.length
    };
  }, [state.conversationMessages.length, state.threadId]);

  useEffect(() => {
    if (appSurface !== "ads") {
      setArchiveLoadState("idle");
      return;
    }

    let isActive = true;
    const sessionCreatives = readGeneratedCreatives();
    const cachedArchiveCreatives = readArchiveCreativesCache();
    const initialCreatives = mergeArchiveCreatives(sessionCreatives, cachedArchiveCreatives);
    setGeneratedCreatives(initialCreatives);
    setArchiveLoadState(initialCreatives.length > 0 ? "ready" : "loading");

    void listArchiveItems({ limit: 20, includeTotal: false })
      .then((response) => {
        if (!isActive) {
          return;
        }

        const archivedCreatives = response.items
          .map(archiveItemToCreative)
          .filter((creative): creative is MockCreative => Boolean(creative));

        // Show both local (this-device) and server-saved results instead of
        // discarding either; dedupe by id (session ids are `generated-<jobId>`,
        // archive ids are adIds, so overlap is rare but guarded).
        writeArchiveCreativesCache(archivedCreatives);
        setGeneratedCreatives(mergeArchiveCreatives(sessionCreatives, archivedCreatives));
        setArchiveLoadState("ready");
      })
      .catch(() => {
        if (isActive) {
          setGeneratedCreatives(initialCreatives);
          setArchiveLoadState(initialCreatives.length > 0 ? "ready" : "error");
        }
      });

    return () => {
      isActive = false;
    };
  }, [appSurface, archiveReloadToken]);

  useEffect(() => {
    if (appSurface !== "chat") {
      lastPrimedStageRef.current = null;
      return;
    }

    if (jobIdParam && initialStage !== "start") {
      let isActive = true;
      Promise.resolve()
        .then(async () => {
          const jobResponse = await getGenerationJob(jobIdParam);
          const job = jobResponse.job;
          const routeThreadId = toGenerationJobThreadId(job.thread_id || threadIdParam);
          let restoreState = null;
          let transcript: ChatFlowState["conversationMessages"] = [];

          if (routeThreadId) {
            const [stateResponse, messagesResponse] = await Promise.all([
              getChatThreadState(routeThreadId).catch(() => ({ success: true as const, snapshot: null })),
              getChatThreadMessages(routeThreadId, { limit: 120 }).catch(() => ({ success: true as const, messages: [], total: 0 }))
            ]);
            restoreState = mapChatThreadSnapshotToRestoreState(stateResponse.snapshot);
            transcript = mapChatMessagesToTranscript(messagesResponse.messages);
          }

          if (!isActive) {
            return;
          }

          const isRouteFinalImageGeneration = isClientFinalImageGenerationJob(job) || initialStage === "generating" || initialStage === "complete";

          if (restoreState) {
            const turnResponse = generationJobToChatTurnResponse(job, restoreState.copyGenerationMode);
            dispatch({
              type: "restoreThreadSnapshot",
              ...restoreState,
              context: mergeContextFromTurnResponse(restoreState.context, turnResponse),
              generationJob: job,
              conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
            });
          } else if (isRouteFinalImageGeneration) {
            dispatch({ type: "showResultShell" });
            dispatch({ type: "generationJobUpdated", generationJob: job });
          } else {
            const pendingTurn = readChatTurnSnapshot();
            if (chatTurnSnapshotMatchesThread(pendingTurn, routeThreadId)) {
              restoreChatTurnSnapshot(pendingTurn);
              return;
            }
            dispatch({ type: "generationJobUpdated", generationJob: job });
          }

          clearGenerationFailureSnapshot();
          setShowHistory(false);

          if (job.status === "waiting_user_input") {
            const restoreIntake: InitialChatIntakeContext | undefined = restoreState
              ? {
                  prompt: restoreState.prompt,
                  copyGenerationMode: restoreState.copyGenerationMode,
                  imageGenerationEngine: restoreState.selectedImageGenerationEngine,
                  sourceImagePath: restoreState.sourceImagePath,
                  referenceImagePath: restoreState.referenceImagePath,
                  selectedReferenceTemplateId: restoreState.selectedReferenceTemplateId,
                  selectedReferenceTemplateTitle: restoreState.selectedReferenceTemplateTitle,
                  userCustomHeadline: restoreState.userCustomHeadline,
                  userCustomSubcopy: restoreState.userCustomSubcopy
                }
              : undefined;
            // 라이브 job의 pending_interrupt로 stage 결정 — 스냅샷 currentQuestion 의존 제거.
            // option_question / copy_candidate_selection / custom_copy_input 모두 단일 디사이더로 처리.
            if (stopForGenerationJobInterrupt(job, restoreIntake)) {
              lastPrimedStageRef.current = isRouteFinalImageGeneration ? "generating" : "start";
              return;
            }
          }

          if (isTerminalGenerationJobStatus(job.status)) {
            setGenerationStage("complete");
            lastPrimedStageRef.current = "complete";
            return;
          }

          setGenerationStage(isRouteFinalImageGeneration ? "generating" : "jobQuestion");
          lastPrimedStageRef.current = isRouteFinalImageGeneration ? "generating" : "start";
          void pollGenerationJobUntilDoneOrQuestion(job);
        })
        .catch(() => {
          if (!isActive) {
            return;
          }
          const failure = readGenerationFailureSnapshot();
          if (failure) {
            dispatch({ type: "showGenerationFailure", ...failure });
            setGenerationStage("complete");
            lastPrimedStageRef.current = "complete";
            return;
          }
          dispatch({ type: "showGenerationFailure", message: "생성 요청 상태를 불러오지 못했어요. 잠시 후 다시 시도해주세요." });
          setGenerationStage("complete");
          lastPrimedStageRef.current = "complete";
        });

      return () => {
        isActive = false;
      };
    }

    if (threadIdParam) {
      const activeThread = activeThreadRef.current;
      if (threadIdParam === activeThread.threadId && activeThread.conversationMessageCount > 0) {
        return;
      }

      Promise.all([
        getChatThreadState(threadIdParam),
        getChatThreadMessages(threadIdParam, { limit: 120 }).catch(() => ({ success: true as const, messages: [], total: 0 }))
      ]).then(([stateResponse, messagesResponse]) => {
        const restoreState = mapChatThreadSnapshotToRestoreState(stateResponse.snapshot);
        if (!restoreState) {
          const pendingTurn = readChatTurnSnapshot();
          if (chatTurnSnapshotMatchesThread(pendingTurn, threadIdParam)) {
            restoreChatTurnSnapshot(pendingTurn);
            return;
          }
          showToast("대화 기록을 불러왔지만 이어갈 정보가 비어 있어요.");
          return;
        }

        const transcript = mapChatMessagesToTranscript(messagesResponse.messages);
        dispatch({
          type: "restoreThreadSnapshot",
          ...restoreState,
          conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
        });
        setShowHistory(false);
        const restoreIntake: InitialChatIntakeContext = {
          prompt: restoreState.prompt,
          copyGenerationMode: restoreState.copyGenerationMode,
          imageGenerationEngine: restoreState.selectedImageGenerationEngine,
          sourceImagePath: restoreState.sourceImagePath,
          referenceImagePath: restoreState.referenceImagePath,
          selectedReferenceTemplateId: restoreState.selectedReferenceTemplateId,
          selectedReferenceTemplateTitle: restoreState.selectedReferenceTemplateTitle,
          userCustomHeadline: restoreState.userCustomHeadline,
          userCustomSubcopy: restoreState.userCustomSubcopy
        };
        // interrupt(라이브 상태)가 스냅샷보다 우선. waiting이면 단일 디사이더로 stage 결정.
        if (
          restoreState.generationJob.status === "waiting_user_input" &&
          stopForGenerationJobInterrupt(restoreState.generationJob, restoreIntake)
        ) {
          return;
        }
        if (isTerminalGenerationJobStatus(restoreState.generationJob.status)) {
          setGenerationStage("complete");
          lastPrimedStageRef.current = "complete";
          return;
        }
        setGenerationStage(restoreState.currentQuestion ? "jobQuestion" : "brief");
        lastPrimedStageRef.current = restoreState.currentQuestion ? "generating" : "brief";
      }).catch(() => {
        showToast("대화 기록을 불러오는데 실패했습니다.");
      });
      return;
    }

    if (initialStage === "start") {
      if (consumeFreshGenerationRequest()) {
        clearChatFlowSnapshot();
        clearChatTurnSnapshot();
        clearGenerationFailureSnapshot();
        dispatch({ type: "reset" });
        setGenerationStage("brief");
        lastPrimedStageRef.current = "start";
        return;
      }

      const snapshot = readChatFlowSnapshot();
      if (snapshot) {
        clearChatTurnSnapshot();
        restoreBriefSnapshot(snapshot, "start");
        return;
      }

      const pendingTurn = readChatTurnSnapshot();
      if (pendingTurn) {
        restoreChatTurnSnapshot(pendingTurn);
        return;
      }

      if (lastPrimedStageRef.current === "start") {
        return;
      }
      clearChatFlowSnapshot();
      clearChatTurnSnapshot();
      dispatch({ type: "reset" });
      setGenerationStage("brief");
      lastPrimedStageRef.current = "start";
      return;
    }

    if (lastPrimedStageRef.current === initialStage) {
      return;
    }

    const snapshot = readChatFlowSnapshot();
    if (snapshot) {
      restoreBriefSnapshot(snapshot, initialStage);
      return;
    }

    const failure = readGenerationFailureSnapshot();
    if (failure) {
      dispatch({ type: "showGenerationFailure", ...failure });
      setGenerationStage("complete");
      lastPrimedStageRef.current = initialStage;
      return;
    }

    dispatch({ type: "reset" });
    dispatch({ type: "showResultShell" });
    setGenerationStage("complete");
    lastPrimedStageRef.current = initialStage;
  }, [appSurface, applyTurnResponse, initialStage, jobIdParam, restoreBriefSnapshot, restoreChatTurnSnapshot, threadIdParam]);

  useEffect(() => {
    const job = state.generationJob;
    if (appSurface !== "chat" || generationStage !== "complete" || !job || isTerminalGenerationJobStatus(job.status)) {
      return;
    }

    let isActive = true;
    const initialJob = job;

    async function pollNonTerminalCompleteJob() {
      let currentJob = initialJob;
      while (isActive && !isTerminalGenerationJobStatus(currentJob.status)) {
        await delay(GENERATION_JOB_POLL_INTERVAL_MS);
        if (!isActive) {
          return;
        }

        try {
          const response = await getGenerationJob(currentJob.job_id);
          currentJob = response.job;
          if (!isActive) {
            return;
          }
          dispatch({ type: "generationJobUpdated", generationJob: currentJob });
        } catch {
          return;
        }
      }
    }

    void pollNonTerminalCompleteJob();

    return () => {
      isActive = false;
    };
  }, [appSurface, generationStage, state.generationJob?.job_id, state.generationJob?.status]);

  async function handleSubmitPrompt(prompt: string, options: GenerationStartOptions = {}) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    const selectedReferenceTemplateId = (options.selectedReferenceTemplateId ?? readGenerationDraftReferenceTemplateId()) || undefined;
    const requestContext = readGenerationRequestContext();
    const imageGenerationEngine = options.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE;
    const engineOption = getGenerationEngineOption(imageGenerationEngine);
    const backendEngine = resolveGenerationEnginePreference(imageGenerationEngine);
    clearGenerationDraftPrompt();
    dispatch({
      type: "submitPrompt",
      prompt,
      copyGenerationMode: options.copyGenerationMode,
      imageGenerationEngine,
      userCustomHeadline: options.userCustomHeadline ?? null,
      userCustomSubcopy: options.userCustomSubcopy ?? null
    });
    if (selectedReferenceTemplateId) {
      dispatch({
        type: "referenceTemplateSelected",
        selectedReferenceTemplateId,
        selectedReferenceTemplateTitle: requestContext?.selectedReferenceTemplateTitle ?? null
      });
    }
    try {
      const uploadedReference = options.referenceImageFile ? await uploadReferenceAsset(options.referenceImageFile) : null;
      const referenceImagePath = options.referenceImagePath ?? uploadedReference?.referenceImagePath ?? undefined;
      const turnSnapshotBase = {
        prompt,
        copyGenerationMode: options.copyGenerationMode,
        imageGenerationEngine,
        sourceImagePath: null,
        referenceImagePath: referenceImagePath ?? null,
        selectedReferenceTemplateId: selectedReferenceTemplateId ?? null,
        selectedReferenceTemplateTitle: requestContext?.selectedReferenceTemplateTitle ?? null,
        userCustomHeadline: options.userCustomHeadline ?? null,
        userCustomSubcopy: options.userCustomSubcopy ?? null
      };
      if (referenceImagePath) {
        dispatch({
          type: "submitPrompt",
          prompt,
          copyGenerationMode: options.copyGenerationMode,
          imageGenerationEngine,
          referenceImagePath,
          userCustomHeadline: options.userCustomHeadline ?? null,
          userCustomSubcopy: options.userCustomSubcopy ?? null,
          transcriptMode: "update_current_turn"
        });
      }
      const activeThreadId = toGenerationJobThreadId(threadIdParam || state.threadId);
      const response = await createGenerationJob({
        userInput: appendSavedBrandKitContext(prompt),
        threadId: activeThreadId,
        ...(options.adFormat ? { adFormat: options.adFormat } : {}),
        runMode: "graph_job",
        copyGenerationMode: options.copyGenerationMode ?? undefined,
        selectedReferenceTemplateId: selectedReferenceTemplateId ?? undefined,
        referenceImagePath,
        userCustomHeadline: options.userCustomHeadline ?? undefined,
        userCustomSubcopy: options.userCustomSubcopy ?? undefined,
        metadata: {
          source: "web_chat_intake",
          selected_engine: imageGenerationEngine,
          requested_engine: backendEngine,
          t2i_engine: backendEngine,
          selected_engine_label: engineOption.modelName,
          selected_reference_template_id: selectedReferenceTemplateId ?? null,
          reference_template_title: requestContext?.selectedReferenceTemplateTitle ?? null,
          reference_image_path: referenceImagePath ?? null,
          copy_generation_mode: options.copyGenerationMode ?? null
        }
      });

      if (shouldPollInitialGenerationJob(response.job)) {
        writeChatTurnSnapshot({
          ...turnSnapshotBase,
          generationJob: response.job,
          response: null
        });
        setOptimisticSurface("chat");
        await pollGenerationJobUntilDoneOrQuestion(response.job, {
          prompt,
          copyGenerationMode: options.copyGenerationMode,
          imageGenerationEngine,
          sourceImagePath: null,
          referenceImagePath: referenceImagePath ?? null,
          selectedReferenceTemplateId: selectedReferenceTemplateId ?? null,
          selectedReferenceTemplateTitle: requestContext?.selectedReferenceTemplateTitle ?? null,
          userCustomHeadline: options.userCustomHeadline ?? null,
          userCustomSubcopy: options.userCustomSubcopy ?? null
        });
        return;
      }

      const pendingInterrupt = getPendingGenerationJobParsedInterrupt(response.job);
      if (
        response.job.status === "waiting_user_input" &&
        pendingInterrupt &&
        pendingInterrupt.type !== "option_question"
      ) {
        // Copy-selection / custom-copy interrupts must stop for an explicit user choice,
        // not auto-pick the recommended candidate. Route through the same interrupt handler
        // as the polled path so both entry paths behave identically. option_question keeps
        // its existing intake-step rendering below.
        writeChatTurnSnapshot({
          ...turnSnapshotBase,
          generationJob: response.job,
          response: null
        });
        setOptimisticSurface("chat");
        stopForGenerationJobInterrupt(response.job, {
          prompt,
          copyGenerationMode: options.copyGenerationMode,
          imageGenerationEngine,
          sourceImagePath: null,
          referenceImagePath: referenceImagePath ?? null,
          selectedReferenceTemplateId: selectedReferenceTemplateId ?? null,
          selectedReferenceTemplateTitle: requestContext?.selectedReferenceTemplateTitle ?? null,
          userCustomHeadline: options.userCustomHeadline ?? null,
          userCustomSubcopy: options.userCustomSubcopy ?? null
        });
        return;
      }

      const turnResponse = generationJobToChatTurnResponse(response.job, options.copyGenerationMode);
      writeChatTurnSnapshot({
        ...turnSnapshotBase,
        generationJob: response.job,
        response: turnResponse
      });
      applyTurnResponse(
        prompt,
        turnResponse,
        imageGenerationEngine,
        null,
        referenceImagePath ?? null,
        options.userCustomHeadline ?? null,
        options.userCustomSubcopy ?? null
      );

      if (!threadIdParam && response.job.thread_id) {
         router.replace(`?threadId=${response.job.thread_id}`);
      }
    } catch (error) {
      writeGenerationDraftPrompt(prompt);
      if (selectedReferenceTemplateId) {
        writeGenerationDraftReferenceTemplateId(selectedReferenceTemplateId);
      }
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "생성 요청에 실패했습니다. 잠시 후 다시 시도해주세요.",
        errorCode: error instanceof ApiError ? error.errorCode : undefined,
        recoverToStart: true
      });
    }
  }

  function createInitialChatIntakeFromState(): InitialChatIntakeContext {
    return {
      prompt: state.userInput,
      copyGenerationMode: state.copyGenerationMode,
      imageGenerationEngine: state.selectedImageGenerationEngine,
      sourceImagePath: state.sourceImagePath ?? null,
      referenceImagePath: state.referenceImagePath ?? null,
      selectedReferenceTemplateId: state.selectedReferenceTemplateId ?? null,
      selectedReferenceTemplateTitle: state.selectedReferenceTemplateTitle ?? null,
      userCustomHeadline: state.userCustomHeadline ?? null,
      userCustomSubcopy: state.userCustomSubcopy ?? null
    };
  }

  async function handleAnswerQuestion(input: { value: string; label: string; customText?: string }) {
    if (!state.currentQuestion || !state.jobId || !state.threadId) {
      return;
    }

    dispatch({ type: "submitQuestionAnswer", label: input.label });
    try {
      if (state.generationJob?.status === "waiting_user_input") {
        const answerPayload = {
          field: state.currentQuestion.field,
          value: input.value,
          ...(input.customText ? { customText: input.customText } : {}),
          displayText: input.label
        };
        const response = await answerGenerationJob(state.jobId, answerPayload);
        await pollGenerationJobUntilDoneOrQuestion(response.job, createInitialChatIntakeFromState());
        return;
      }

      const response = await answerChatQuestion({
        jobId: state.jobId,
        threadId: state.threadId,
        field: state.currentQuestion.field,
        value: input.value,
        customText: input.customText
      });
      applyTurnResponse(
        state.userInput,
        response,
        state.selectedImageGenerationEngine,
        state.sourceImagePath ?? null,
        state.referenceImagePath ?? null,
        state.userCustomHeadline,
        state.userCustomSubcopy
      );
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "답변 전송에 실패해 다시 시도해주세요.",
        errorCode: error instanceof ApiError ? error.errorCode : undefined
      });
    }
  }

  async function handleStartPhotoGeneration(input: PhotoGenerateInput) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    setGenerationStage("brief");

    try {
      const upload = await uploadPhotoAsset(input.file);
      const response = await startPhotoGeneration({
        userInput: appendSavedBrandKitContext(input.prompt),
        sourceImagePath: upload.sourceImagePath,
        copyGenerationMode: input.copyGenerationMode,
        userCustomHeadline: input.userCustomHeadline,
        userCustomSubcopy: input.userCustomSubcopy,
        selectedReferenceTemplateId: input.selectedReferenceTemplateId,
        referenceImagePath: input.referenceImagePath
      });
      writeChatTurnSnapshot({
        prompt: input.prompt,
        response,
        copyGenerationMode: input.copyGenerationMode,
        imageGenerationEngine: input.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
        sourceImagePath: upload.sourceImagePath,
        referenceImagePath: input.referenceImagePath ?? null,
        userCustomHeadline: input.userCustomHeadline ?? null,
        userCustomSubcopy: input.userCustomSubcopy ?? null
      });
      lastPrimedStageRef.current = null;
      navigateTo("chat", "start");
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : "사진 기반 생성 요청에 실패했습니다. 파일과 서버 연결을 확인해주세요.");
    }
  }

  function buildChatFlowSnapshot(brief: ChatBrief, customDirection = state.customDirection): ChatFlowSnapshot {
    return {
      prompt: state.userInput,
      jobId: state.jobId,
      threadId: state.threadId,
      context: state.inferredContext,
      copyCandidates: state.copyCandidates,
      copyCandidateSource: state.copyCandidateSource,
      copyCandidateOrigin: state.copyCandidateOrigin,
      selectedCopyId: state.copyGenerationMode === "suggest_candidates" ? "" : state.selectedCopyId,
      selectedChannelId: state.selectedChannelId,
      selectedTone: state.selectedTone,
      customDirection,
      userCustomHeadline: state.userCustomHeadline,
      userCustomSubcopy: state.userCustomSubcopy,
      brief,
      selectedReferenceTemplateId: state.selectedReferenceTemplateId,
      selectedReferenceTemplateTitle: state.selectedReferenceTemplateTitle,
      imageGenerationEngine: state.selectedImageGenerationEngine,
      sourceImagePath: state.sourceImagePath ?? null,
      referenceImagePath: state.referenceImagePath ?? null
    };
  }

  async function handleContinueToBrief() {
    if (!state.jobId || !state.threadId) {
      dispatch({
        type: "backendRequestFailed",
        message: "생성 연결 정보가 없어 실제 이미지 생성을 시작할 수 없습니다. 첫 요청을 다시 보내주세요.",
        errorCode: undefined
      });
      return;
    }

    dispatch({ type: "beginBriefRequest" });

    if (state.copyGenerationMode === "suggest_candidates") {
      const brief = buildDeferredCopyBrief(state);
      const snapshot = buildChatFlowSnapshot(brief);
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      dispatch({ type: "backendBriefSucceeded", brief });
      dispatch({ type: "continueToBrief" });
      return;
    }

    try {
      const response = await createChatBrief({
        jobId: state.jobId,
        threadId: state.threadId,
        selectedCopyId: state.selectedCopyId,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone,
        customDirection: state.customDirection
      });
      const snapshot = buildChatFlowSnapshot(response.brief);
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      setGeneratedCreatives(response.brief.finalImagePath ? addGeneratedCreativeSnapshot(snapshot) : readGeneratedCreatives());
      dispatch({ type: "backendBriefSucceeded", brief: response.brief });
      dispatch({ type: "continueToBrief" });
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "브리프와 이미지 생성에 실패했습니다. 설정을 확인한 뒤 다시 시도해주세요.",
        errorCode: error instanceof ApiError ? error.errorCode : undefined
      });
    }
  }

  async function handleRefineBrief(message: string) {
    const refinement = message.trim();
    if (!refinement) {
      return;
    }
    if (!state.jobId || !state.threadId) {
      dispatch({
        type: "backendRequestFailed",
        message: "브리프를 다시 정리할 연결 정보가 없어요. 첫 요청을 다시 보내주세요."
      });
      return;
    }

    const nextCustomDirection = mergeBriefRefinement(state.customDirection, refinement);
    dispatch({ type: "submitBriefRefinement", message: refinement, customDirection: nextCustomDirection });

    if (state.copyGenerationMode === "suggest_candidates") {
      const brief = buildDeferredCopyBrief(state, nextCustomDirection);
      const snapshot = buildChatFlowSnapshot(brief, nextCustomDirection);
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      dispatch({ type: "briefRefinementSucceeded", brief });
      dispatch({ type: "continueToBrief" });
      return;
    }

    try {
      const response = await createChatBrief({
        jobId: state.jobId,
        threadId: state.threadId,
        selectedCopyId: state.selectedCopyId,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone,
        customDirection: nextCustomDirection
      });
      const snapshot = buildChatFlowSnapshot(response.brief, nextCustomDirection);
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      setGeneratedCreatives(response.brief.finalImagePath ? addGeneratedCreativeSnapshot(snapshot) : readGeneratedCreatives());
      dispatch({ type: "briefRefinementSucceeded", brief: response.brief });
      dispatch({ type: "continueToBrief" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "추가 요청을 브리프에 반영하지 못했어요. 잠시 뒤 다시 시도해주세요.";
      dispatch({
        type: "backendRequestFailed",
        message,
        errorCode: error instanceof ApiError ? error.errorCode : undefined
      });
      throw new Error(message);
    }
  }

  function stopForGenerationJobInterrupt(job: GenerationJob, initialChatIntake?: InitialChatIntakeContext): boolean {
    const interrupt = getPendingGenerationJobParsedInterrupt(job);
    if (!interrupt) {
      return false;
    }

    if (interrupt.type === "option_question") {
      const incoming = interrupt.optionQuestion;
      // 동일 질문 재-dispatch 스킵 — 폴링/리마운트 churn(깜빡임) 방지.
      const isSameQuestion =
        !!state.currentQuestion &&
        state.currentQuestion.field === incoming.field &&
        state.currentQuestion.question === incoming.question;
      if (!isSameQuestion) {
        const turnResponse = generationJobToChatTurnResponse(job, initialChatIntake?.copyGenerationMode ?? state.copyGenerationMode);
        const context = isQuestionResponse(turnResponse) ? turnResponse.context : {};
        dispatch({
          type: "generationJobQuestionReceived",
          generationJob: job,
          question: incoming,
          context,
          sourceImagePath: initialChatIntake?.sourceImagePath ?? null,
          referenceImagePath: initialChatIntake?.referenceImagePath ?? null
        });
      }
    } else {
      dispatch({ type: "generationJobInterruptReceived", generationJob: job });
    }
    setGenerationStage("jobQuestion");
    lastPrimedStageRef.current = "start";
    setOptimisticSurface("chat");
    return true;
  }

  async function pollGenerationJobUntilDoneOrQuestion(initialJob: GenerationJob, initialChatIntake?: InitialChatIntakeContext): Promise<GenerationJob> {
    let currentJob = initialJob;
    dispatch({ type: "generationJobUpdated", generationJob: currentJob });

    if (stopForGenerationJobInterrupt(currentJob, initialChatIntake)) {
      return currentJob;
    }

    for (let attempt = 0; attempt < GENERATION_JOB_MAX_POLLS && !isTerminalGenerationJobStatus(currentJob.status); attempt += 1) {
      if (attempt > 0) {
        await delay(GENERATION_JOB_POLL_INTERVAL_MS);
      }
      const response = await getGenerationJob(currentJob.job_id);
      currentJob = response.job;
      dispatch({ type: "generationJobUpdated", generationJob: currentJob });

      if (stopForGenerationJobInterrupt(currentJob, initialChatIntake)) {
        return currentJob;
      }
    }

    if (currentJob.status === "waiting_user_input") {
      throw new Error("추가 질문 정보를 받지 못했어요. 잠시 후 다시 시도해주세요.");
    }

    if (initialChatIntake && currentJob.status !== "failed" && currentJob.status !== "cancelled") {
      const turnResponse = generationJobToChatTurnResponse(currentJob, initialChatIntake.copyGenerationMode);
      writeChatTurnSnapshot({
        ...initialChatIntake,
        generationJob: currentJob,
        response: turnResponse
      });
      applyTurnResponse(
        initialChatIntake.prompt,
        turnResponse,
        initialChatIntake.imageGenerationEngine,
        initialChatIntake.sourceImagePath ?? null,
        initialChatIntake.referenceImagePath ?? null,
        initialChatIntake.userCustomHeadline ?? null,
        initialChatIntake.userCustomSubcopy ?? null
      );
      setGenerationStage("brief");
      lastPrimedStageRef.current = "start";
      setOptimisticSurface("chat");
      router.replace(buildChatStageHrefWithJob("start", { threadId: currentJob.thread_id }));
      return currentJob;
    }

    setGenerationStage("complete");
    lastPrimedStageRef.current = "complete";
    clearGenerationFailureSnapshot();
    setOptimisticSurface("chat");
    router.push(buildChatStageHrefForJob("complete", currentJob));
    return currentJob;
  }

  async function handleAnswerGenerationJobQuestion(input: { value: string; label: string; customText?: string }) {
    const question = state.currentQuestion;
    const jobId = state.generationJob?.job_id;
    if (!question || !jobId) {
      return;
    }

    dispatch({ type: "submitGenerationJobAnswer", label: input.label });

    try {
      const shouldShowFinalGenerationProgress = isClientFinalImageGenerationJob(state.generationJob);
      const answerPayload = {
        field: question.field,
        value: input.value,
        displayText: input.label,
        ...(input.customText ? { customText: input.customText } : {})
      };
      const response = await answerGenerationJob(jobId, answerPayload);
      if (shouldShowFinalGenerationProgress) {
        setGenerationStage("generating");
        lastPrimedStageRef.current = "generating";
        await pollGenerationJobUntilDoneOrQuestion(response.job);
        return;
      }
      setGenerationStage("jobQuestion");
      lastPrimedStageRef.current = "start";
      await pollGenerationJobUntilDoneOrQuestion(response.job, createInitialChatIntakeFromState());
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "추가 정보를 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }

  async function handleSelectGenerationJobCopyCandidate(input: { selectedCopyId: string; label: string }) {
    const jobId = state.generationJob?.job_id;
    if (!jobId) {
      return;
    }

    dispatch({ type: "submitGenerationJobAnswer", label: input.label });

    try {
      const shouldShowFinalGenerationProgress = isClientFinalImageGenerationJob(state.generationJob);
      const response = await answerGenerationJob(jobId, {
        selectedCopyId: input.selectedCopyId,
        displayText: input.label,
        payload: {
          selected_channel_id: state.selectedChannelId || undefined,
          selected_ad_format: toCanonicalAdFormat(state.selectedChannelId),
          selected_tone: state.selectedTone || undefined,
          custom_direction: state.customDirection || undefined
        }
      });
      if (shouldShowFinalGenerationProgress) {
        setGenerationStage("generating");
        lastPrimedStageRef.current = "generating";
        await pollGenerationJobUntilDoneOrQuestion(response.job);
        return;
      }
      setGenerationStage("jobQuestion");
      lastPrimedStageRef.current = "start";
      await pollGenerationJobUntilDoneOrQuestion(response.job, createInitialChatIntakeFromState());
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "선택한 문구를 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }

  async function handleSubmitGenerationJobCustomCopy(input: {
    userCustomHeadline: string;
    userCustomSubcopy?: string;
    label: string;
  }) {
    const jobId = state.generationJob?.job_id;
    if (!jobId) {
      return;
    }

    dispatch({ type: "submitGenerationJobAnswer", label: input.label });

    try {
      const shouldShowFinalGenerationProgress = isClientFinalImageGenerationJob(state.generationJob);
      const pendingInterrupt = getPendingGenerationJobParsedInterrupt(state.generationJob);
      const candidateSelectionPayload =
        pendingInterrupt?.type === "copy_candidate_selection"
          ? {
              selected_channel_id: state.selectedChannelId || undefined,
              selected_ad_format: toCanonicalAdFormat(state.selectedChannelId),
              selected_tone: state.selectedTone || undefined,
              custom_direction: state.customDirection || undefined
            }
          : undefined;
      const response = await answerGenerationJob(jobId, {
        displayText: input.label,
        userCustomHeadline: input.userCustomHeadline,
        ...(input.userCustomSubcopy ? { userCustomSubcopy: input.userCustomSubcopy } : {}),
        ...(candidateSelectionPayload ? { payload: candidateSelectionPayload } : {})
      });
      if (shouldShowFinalGenerationProgress) {
        setGenerationStage("generating");
        lastPrimedStageRef.current = "generating";
        await pollGenerationJobUntilDoneOrQuestion(response.job);
        return;
      }
      setGenerationStage("jobQuestion");
      lastPrimedStageRef.current = "start";
      await pollGenerationJobUntilDoneOrQuestion(response.job, createInitialChatIntakeFromState());
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "입력한 문구를 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }

  async function handleComplianceAction(action: { id: string; label: string; available: boolean }) {
    const jobId = state.generationJob?.job_id;
    if (!jobId) {
      return;
    }

    dispatch({ type: "submitGenerationJobAnswer", label: action.label });

    try {
      const shouldShowFinalGenerationProgress = isClientFinalImageGenerationJob(state.generationJob);
      const response = await answerGenerationJob(jobId, {
        action: action.id,
        displayText: action.label
      });
      if (shouldShowFinalGenerationProgress) {
        setGenerationStage("generating");
        lastPrimedStageRef.current = "generating";
        await pollGenerationJobUntilDoneOrQuestion(response.job);
        return;
      }
      setGenerationStage("jobQuestion");
      lastPrimedStageRef.current = "start";
      await pollGenerationJobUntilDoneOrQuestion(response.job, createInitialChatIntakeFromState());
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "선택을 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }

  async function handleOpenGeneratedResult() {
    const engine = state.selectedImageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE;
    const engineOption = getGenerationEngineOption(engine);
    const backendEngine = resolveGenerationEnginePreference(engine);
    const isDeferredCopySelection = state.copyGenerationMode === "suggest_candidates";
    const selectedCopy = state.copyCandidates.find((copy) => copy.id === state.selectedCopyId) ?? null;
    const finalCopyGenerationMode = state.copyGenerationMode;
    const finalSelectedCopyId = isDeferredCopySelection ? null : state.selectedCopyId || undefined;
    const finalUserCustomHeadline = isDeferredCopySelection ? undefined : state.userCustomHeadline || undefined;
    const finalUserCustomSubcopy = isDeferredCopySelection ? undefined : state.userCustomSubcopy || undefined;
    const finalAdFormat = toCanonicalAdFormat(state.selectedChannelId) ?? "instagram_feed";
    const selectedReferenceTemplateId = state.selectedReferenceTemplateId || readGenerationDraftReferenceTemplateId() || undefined;
    const sourceImagePath = state.sourceImagePath || undefined;
    const referenceImagePath = state.referenceImagePath || undefined;
    const requestUserInput = appendSavedBrandKitContext(buildGenerationJobUserInput(state));

    clearGenerationFailureSnapshot();
    dispatch({ type: "generationJobRequested" });
    // 생성 잡 생성 전에는 URL을 바꾸지 않음. navigateTo("chat","generating")는 jobId 없는
    // `?stage=generating`로 push해 복원 useEffect를 jobId 부재 상태로 재실행시키고,
    // initialStage/jobIdParam 비동기 갱신 틈에 fallback 분기가 stage="complete"를
    // 잠깐 렌더(생성실패 플래시)하게 만들었음. surface/stage는 로컬 state로만 전환하고
    // URL은 jobId가 생긴 뒤(router.replace) 한 번만 갱신함.
    setOptimisticSurface("chat");
    setGenerationStage("generating");
    lastPrimedStageRef.current = "generating";

    try {
      const created = await createGenerationJob({
        userInput: requestUserInput,
        threadId: toGenerationJobThreadId(state.threadId),
        entryMode: state.entryMode,
        copyGenerationMode: finalCopyGenerationMode,
        adFormat: finalAdFormat,
        runMode: resolveGenerationRunMode(engine),
        selectedReferenceTemplateId,
        sourceImagePath,
        referenceImagePath,
        selectedCopyId: finalSelectedCopyId,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone || undefined,
        customDirection: state.customDirection,
        userCustomHeadline: finalUserCustomHeadline || undefined,
        userCustomSubcopy: finalUserCustomSubcopy || undefined,
        metadata: {
          source: "web_generation_flow",
          source_image_path: sourceImagePath ?? null,
          reference_image_path: referenceImagePath ?? null,
          selected_engine: engine,
          requested_engine: backendEngine,
          t2i_engine: backendEngine,
          selected_engine_label: engineOption.modelName,
          selected_copy_id: finalSelectedCopyId ?? null,
          legacy_preview_copy_id: isDeferredCopySelection ? state.selectedCopyId || null : null,
          legacy_preview_copy_headline: isDeferredCopySelection ? selectedCopy?.headline ?? null : null,
          selected_channel_id: state.selectedChannelId,
          selected_ad_format: finalAdFormat,
          selected_tone: state.selectedTone || null,
          copy_generation_mode: finalCopyGenerationMode,
          original_copy_generation_mode: state.copyGenerationMode,
          user_custom_headline: finalUserCustomHeadline || null,
          user_custom_subcopy: finalUserCustomSubcopy || null,
          reference_template_title: state.selectedReferenceTemplateTitle || null,
          final_brief: buildGenerationJobBriefMetadata(state)
        }
      });

      finalGenerationJobIdsRef.current.add(created.job.job_id);
      router.replace(buildChatStageHrefForJob("generating", created.job));
      await pollGenerationJobUntilDoneOrQuestion(created.job);
    } catch (error) {
      const message = error instanceof Error ? error.message : "이미지 생성 요청에 실패했습니다. 잠시 후 다시 시도해주세요.";
      writeGenerationFailureSnapshot({
        message,
        threadId: state.threadId,
        userInput: state.userInput,
        imageGenerationEngine: engine
      });
      dispatch({
        type: "showGenerationFailure",
        message,
        threadId: state.threadId,
        userInput: state.userInput,
        imageGenerationEngine: engine
      });
      setGenerationStage("complete");
      lastPrimedStageRef.current = "complete";
      navigateTo("chat", "complete");
    }
  }

  function handleOpenFreshChat() {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    clearGenerationDraftPrompt();
    dispatch({ type: "reset" });
    setGenerationStage("brief");
    navigateTo("chat", "start");
  }

  function handleUseReferenceTemplate(template: ReferenceTemplateCard) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    dispatch({ type: "reset" });
    setGenerationStage("brief");
    clearGenerationDraftPrompt();
    saveGenerationRequestContext({
      selectedReferenceTemplateId: template.templateId,
      selectedReferenceTemplateTitle: template.title,
      source: "reference_gallery"
    });
    showToast(`${template.title} 스타일을 다음 요청에 연결했어요.`);
    navigateTo("chat", "start");
  }

  function handleBackToFlowEntry() {
    navigateTo(readChatFlowBackTarget() ?? "studio");
  }

  function handleRegenerateFromRecent() {
    showToast("새 요청 화면에서 비슷하게 만들 광고를 입력해주세요.");
    handleOpenFreshChat();
  }

  function handleRequestCurrentThreadDelete() {
    const threadId = toGenerationJobThreadId(state.threadId || threadIdParam);
    if (!threadId) {
      showToast("아직 삭제할 작업방이 없어요.");
      return;
    }
    setCurrentThreadDeleteError(null);
    setCurrentThreadDeleteOpen(true);
  }

  async function handleConfirmCurrentThreadDelete() {
    const threadId = toGenerationJobThreadId(state.threadId || threadIdParam);
    if (!threadId) {
      setCurrentThreadDeleteOpen(false);
      return;
    }

    setDeletingCurrentThread(true);
    setCurrentThreadDeleteError(null);
    try {
      await archiveChatThread(threadId);
      clearChatFlowSnapshot();
      clearChatTurnSnapshot();
      clearGenerationDraftPrompt();
      dispatch({ type: "reset" });
      setGenerationStage("brief");
      setShowHistory(false);
      setCurrentThreadDeleteOpen(false);
      showToast("작업방을 삭제했어요.");
      navigateTo("studio");
    } catch {
      setCurrentThreadDeleteError("작업방을 삭제하지 못했어요. 생성 중인 작업이라면 완료된 뒤 다시 시도해주세요.");
    } finally {
      setDeletingCurrentThread(false);
    }
  }

  function handleRetryArchiveLoad() {
    setArchiveReloadToken((current) => current + 1);
  }

  async function handleToggleFavoriteGeneratedAd(creative: MockCreative, nextStatus: "saved" | "favorite") {
    if (creative.id.startsWith("generated-")) {
      return;
    }

    try {
      const response = await updateArchiveItem(creative.id, { status: nextStatus });
      const updatedCreative = archiveItemToCreative(response.item);
      upsertArchiveCreativeCacheItem(updatedCreative ?? { ...creative, status: nextStatus });
      setGeneratedCreatives((current) =>
        current.map((item) =>
          item.id === creative.id
            ? updatedCreative ?? { ...item, status: nextStatus }
            : item
        )
      );
      showToast(nextStatus === "favorite" ? `${creative.title}를 즐겨찾기에 추가했어요.` : `${creative.title} 즐겨찾기를 해제했어요.`);
    } catch {
      showToast(`${creative.title} 즐겨찾기를 저장하지 못했어요. 잠시 후 다시 시도해주세요.`);
    }
  }

  async function handleDeleteGeneratedAd(creativeId: string, title: string) {
    if (creativeId.startsWith("generated-")) {
      setGeneratedCreatives(removeGeneratedCreative(creativeId));
      showToast(`${title} 항목을 보관함에서 삭제했어요.`);
      return;
    }

    try {
      await deleteArchiveItem(creativeId);
      removeArchiveCreativeCacheItem(creativeId);
      setGeneratedCreatives((current) => current.filter((item) => item.id !== creativeId));
      showToast(`${title} 항목을 보관함에서 삭제했어요.`);
    } catch {
      showToast(`${title} 항목을 삭제하지 못했어요. 잠시 후 다시 시도해주세요.`);
    }
  }

  async function handleSaveGeneratedCreative(creative: MockCreative) {
    if (!creative.imageUrl) {
      showToast("실제 이미지가 있는 결과만 보관함에 저장할 수 있어요.");
      return;
    }

    const publicJobId = state.jobId || (creative.id.startsWith("generated-") ? creative.id.replace(/^generated-/, "") : undefined);
    try {
      const response = await saveArchiveItem({
        title: creative.title,
        publicJobId,
        imageUrl: creative.imageUrl,
        thumbnailUrl: creative.imageUrl,
        adFormat: creative.format,
        platform: creative.channel,
        source: "generated",
        metadata: {
          subtitle: creative.subtitle,
          fileName: creative.fileName,
          fileType: creative.fileType,
          savedAt: creative.savedAt,
          tags: creative.tags ?? []
        }
      });
      const archivedCreative = archiveItemToCreative(response.item);
      if (archivedCreative) {
        upsertArchiveCreativeCacheItem(archivedCreative);
      }
      setGeneratedCreatives((current) => {
        const updated = current.map((item) => (item.id === creative.id ? { ...item, storage: "내 광고 보관함" } : item));
        if (!archivedCreative) {
          return updated;
        }
        return [archivedCreative, ...updated.filter((item) => item.id !== archivedCreative.id)];
      });
      showToast(`${creative.title}를 보관함에 저장했어요.`);
    } catch {
      showToast(`${creative.title}를 보관함에 저장하지 못했어요. 잠시 후 다시 시도해주세요.`);
    }
  }

  function handleBackFromBrief() {
    setGenerationStage("brief");
    dispatch({ type: "back" });
  }

  function showToast(message: string) {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(null), 3000);
  }

  const hasThreadLimitError = state.errorCode === "thread_limit_reached";
  const displayState = hasThreadLimitError ? { ...state, errorMessage: null } : state;

  return (
    <MobileShell>
      {hasThreadLimitError && <ThreadLimitModal />}
      {appSurface === "home" ? (
        <HomeStartStep
          onOpenStudio={() => navigateTo("studio")}
          onOpenChat={handleOpenFreshChat}
          onOpenPhoto={() => navigateTo("photo")}
          onOpenReference={() => navigateTo("reference")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("my")}
          onOpenNotifications={() => router.push(buildNotificationHref())}
        />
      ) : null}

      {appSurface === "studio" ? (
        <StudioEntryStep
          onGoHome={() => navigateTo("home")}
          onOpenChat={handleOpenFreshChat}
          onOpenPhoto={() => navigateTo("photo")}
          onOpenReference={() => navigateTo("reference")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("my")}
          onOpenThread={(threadId) => {
            writeChatFlowBackTarget("studio");
            setOptimisticSurface("chat");
            router.push(`/generate/chat?threadId=${threadId}`);
          }}
        />
      ) : null}

      {appSurface === "reference" ? (
        <ReferenceBrowseStep
          state={displayState}
          isStandaloneGallery
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("my")}
          onOpenNotifications={() => router.push(buildNotificationHref())}
          onShowProgress={() => navigateTo("studio")}
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={showArchiveStoragePendingToast}
          onUseTemplate={handleUseReferenceTemplate}
        />
      ) : null}

      {appSurface === "ads" ? (
        <RecentAdsStep
          generatedCreatives={generatedCreatives}
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenBrandKit={() => navigateTo("my")}
          onRegenerate={handleRegenerateFromRecent}
          onOpenGeneratedAd={(creativeId) => router.push(buildAdHref(creativeId))}
          onDownloadGeneratedAd={(title) => showToast(`${title} 다운로드는 실제 파일 저장 연결 후 활성화돼요.`)}
          onDeleteGeneratedAd={handleDeleteGeneratedAd}
          onToggleFavoriteGeneratedAd={handleToggleFavoriteGeneratedAd}
          archiveLoadState={archiveLoadState}
          onRetryArchiveLoad={handleRetryArchiveLoad}
          onOpenNotifications={() => router.push(buildNotificationHref())}
        />
      ) : null}

      {appSurface === "my" ? (
        <MyPageStep />
      ) : null}

      {appSurface === "photo" ? (
        <PhotoGenerateStep
          onBack={handleBackToFlowEntry}
          onGoHome={() => navigateTo("home")}
          onOpenChat={handleOpenFreshChat}
          onGenerate={handleStartPhotoGeneration}
        />
      ) : null}

      {showHistory ? (
        <ChatHistoryStep
          onBack={() => setShowHistory(false)}
          onGoHome={() => navigateTo("home")}
          onSelectThread={(threadId) => {
            writeChatFlowBackTarget("studio");
            router.push(`/generate/chat?threadId=${threadId}`);
            setShowHistory(false);
          }}
        />
      ) : appSurface === "chat" && state.step === 1 ? (
        <ChatStartStep
          onSubmit={handleSubmitPrompt}
          onBack={handleBackToFlowEntry}
          onGoHome={() => navigateTo("home")}
          onHistory={() => setShowHistory(true)}
          errorMessage={displayState.errorMessage}
          initialPrompt={state.userInput}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={displayState}
          onBack={() => dispatch({ type: "back" })}
          onAnswer={handleAnswerQuestion}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && !state.currentQuestion && state.isLoading ? (
        <ChatAnalysisPendingStep
          state={displayState}
          onBack={() => dispatch({ type: "back" })}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && !state.currentQuestion && !state.isLoading ? (
        <IntentReviewStep
          state={displayState}
          onBack={() => dispatch({ type: "back" })}
          onSelectTone={(tone) => dispatch({ type: "selectTone", tone })}
          onContinue={() => dispatch({ type: "continueToCopy" })}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 3 ? (
        <CopyChannelStep
          state={displayState}
          onBack={() => dispatch({ type: "back" })}
          onSelectCopy={(copyId) => dispatch({ type: "selectCopy", copyId })}
          onSelectChannel={(channelId) => dispatch({ type: "selectChannel", channelId })}
          onCustomDirection={(value) => dispatch({ type: "setCustomDirection", value })}
          onContinue={handleContinueToBrief}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "brief" ? (
        <BriefConfirmStep
          state={displayState}
          onBack={handleBackFromBrief}
          onGenerate={handleOpenGeneratedResult}
          onRefineBrief={handleRefineBrief}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "jobQuestion" && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={displayState}
          onBack={() => setGenerationStage("brief")}
          onAnswer={handleAnswerGenerationJobQuestion}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" &&
      state.step === 4 &&
      generationStage === "jobQuestion" &&
      !state.currentQuestion &&
      !currentGenerationJobInterrupt &&
      state.isLoading ? (
        <ChatAnalysisPendingStep
          state={displayState}
          onBack={() => setGenerationStage("brief")}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" &&
      state.step === 4 &&
      generationStage === "jobQuestion" &&
      !state.currentQuestion &&
      currentGenerationJobInterrupt &&
      currentGenerationJobInterrupt.type !== "option_question" ? (
        <GenerationJobInterruptStep
          interrupt={currentGenerationJobInterrupt}
          state={displayState}
          isLoading={state.isLoading}
          errorMessage={displayState.errorMessage}
          onBack={() => setGenerationStage("brief")}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
          onSelectCopyCandidate={handleSelectGenerationJobCopyCandidate}
          onSubmitCustomCopy={handleSubmitGenerationJobCustomCopy}
          onComplianceAction={handleComplianceAction}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "generating" ? (
        <GenerationInProgressStep
          state={displayState}
          onBrowse={() => setGenerationStage("browsing")}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "browsing" ? (
        <ReferenceBrowseStep
          state={displayState}
          onShowProgress={() => setGenerationStage("generating")}
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("my")}
          onOpenNotifications={() => router.push(buildNotificationHref())}
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={showArchiveStoragePendingToast}
          onUseTemplate={handleUseReferenceTemplate}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "complete" ? (
        <GenerationCompleteStep
          state={displayState}
          onBrowseSimilar={() => {
            setGenerationStage("similarBrowsing");
            lastPrimedStageRef.current = "similar";
            navigateTo("chat", "similar");
          }}
          onGoHome={() => navigateTo("home")}
          onRegenerate={() => {
            handleOpenFreshChat();
          }}
          onOpenArchive={() => navigateTo("ads")}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "similarBrowsing" ? (
        <ReferenceBrowseStep
          state={displayState}
          isGenerationComplete
          onShowProgress={() => setGenerationStage("complete")}
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("my")}
          onOpenNotifications={() => router.push(buildNotificationHref())}
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={showArchiveStoragePendingToast}
          onUseTemplate={handleUseReferenceTemplate}
        />
      ) : null}

      {isCurrentThreadDeleteOpen ? (
        <div
          className={styles.workspaceDeleteDialogBackdrop}
          role="presentation"
          onClick={() => isDeletingCurrentThread ? undefined : setCurrentThreadDeleteOpen(false)}
        >
          <section
            aria-labelledby="current-thread-delete-title"
            aria-modal="true"
            className={styles.workspaceDeleteDialog}
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div>
              <span className={styles.workspaceDeleteIcon} aria-hidden="true">!</span>
              <h2 id="current-thread-delete-title">이 작업방을 삭제할까요?</h2>
              <p>대화와 진행 상태가 최근 작업방에서 사라져요. 완성된 이미지는 보관함에 남아요.</p>
            </div>
            <strong>{state.userInput || "현재 작업방"}</strong>
            {currentThreadDeleteError ? <p className={styles.workspaceDeleteError}>{currentThreadDeleteError}</p> : null}
            <div className={styles.workspaceDeleteDialogActions}>
              <button disabled={isDeletingCurrentThread} type="button" onClick={() => setCurrentThreadDeleteOpen(false)}>
                취소
              </button>
              <button data-danger="true" disabled={isDeletingCurrentThread} type="button" onClick={handleConfirmCurrentThreadDelete}>
                {isDeletingCurrentThread ? "삭제 중" : "삭제"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      <DashboardToast message={toastMessage} />
    </MobileShell>
  );
}
