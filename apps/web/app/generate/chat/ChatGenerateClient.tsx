"use client";

import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChatHistoryStep } from "@/components/generate/ChatHistoryStep";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
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
  uploadPhotoAsset,
  uploadReferenceAsset,
  type ChatTurnResponse,
  type GenerationJob,
  type GenerationStartOptions,
  type ReferenceTemplateCard
} from "@/lib/api-client";
import { buildAdHref } from "@/lib/ad-navigation";
import { archiveItemToCreative } from "@/lib/archive-creative";
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
  removeGeneratedCreative,
  type GeneratedCreativeSnapshot
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
  readGenerationDraftReferenceTemplateId,
  readGenerationRequestContext,
  saveGenerationRequestContext,
  writeGenerationDraftReferenceTemplateId
} from "@/lib/generation-request-context";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { buildReferenceStyleHref } from "@/lib/reference-navigation";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import type { ChatBrief, ChatFlowState, CopyGenerationMode, InferredContext, OptionQuestion, PartialInferredContext } from "@/types/marketing";
import styles from "@/components/generate/generate.module.css";

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing" | "jobQuestion";

type ChatGenerateClientProps = {
  initialSurface?: DashboardSurface;
  initialStage?: DashboardStage;
};

type ChatFlowSnapshot = GeneratedCreativeSnapshot;
type ChatTurnSnapshot = {
  prompt: string;
  response: ChatTurnResponse;
  copyGenerationMode?: CopyGenerationMode;
  imageGenerationEngine?: ImageGenerationEngine;
  sourceImagePath?: string | null;
  referenceImagePath?: string | null;
  userCustomHeadline?: string | null;
  userCustomSubcopy?: string | null;
};

const CHAT_FLOW_SNAPSHOT_STORAGE_KEY = "easyads_chat_flow_snapshot_v1";
const CHAT_TURN_SNAPSHOT_STORAGE_KEY = "easyads_chat_turn_snapshot_v1";
const CHAT_GENERATION_FAILURE_STORAGE_KEY = "easyads_chat_generation_failure_v1";
const GENERATION_JOB_POLL_INTERVAL_MS = 1800;
const GENERATION_JOB_MAX_POLLS = 80;

type ChatGenerationFailureSnapshot = {
  message: string;
  threadId?: string | null;
  userInput?: string | null;
  imageGenerationEngine?: ImageGenerationEngine | null;
};

function readChatFlowSnapshot(): ChatFlowSnapshot | null {
  try {
    const raw = window.sessionStorage.getItem(CHAT_FLOW_SNAPSHOT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatFlowSnapshot) : null;
  } catch {
    return null;
  }
}

function writeChatFlowSnapshot(snapshot: ChatFlowSnapshot) {
  try {
    window.sessionStorage.setItem(CHAT_FLOW_SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // Navigation should still work if sessionStorage is unavailable.
  }
}

function clearChatFlowSnapshot() {
  try {
    window.sessionStorage.removeItem(CHAT_FLOW_SNAPSHOT_STORAGE_KEY);
  } catch {
    // Ignore storage failures; the in-memory flow can still continue.
  }
}

function readChatTurnSnapshot(): ChatTurnSnapshot | null {
  try {
    const raw = window.sessionStorage.getItem(CHAT_TURN_SNAPSHOT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatTurnSnapshot) : null;
  } catch {
    return null;
  }
}

function writeChatTurnSnapshot(snapshot: ChatTurnSnapshot) {
  try {
    window.sessionStorage.setItem(CHAT_TURN_SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // The in-memory flow will still continue when route state is preserved.
  }
}

function clearChatTurnSnapshot() {
  try {
    window.sessionStorage.removeItem(CHAT_TURN_SNAPSHOT_STORAGE_KEY);
  } catch {
    // Ignore storage failures; a fresh chat can still reset in memory.
  }
}

function readGenerationFailureSnapshot(): ChatGenerationFailureSnapshot | null {
  try {
    const raw = window.sessionStorage.getItem(CHAT_GENERATION_FAILURE_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ChatGenerationFailureSnapshot) : null;
  } catch {
    return null;
  }
}

function writeGenerationFailureSnapshot(snapshot: ChatGenerationFailureSnapshot) {
  try {
    window.sessionStorage.setItem(CHAT_GENERATION_FAILURE_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // The current component state still carries the error when storage is unavailable.
  }
}

function clearGenerationFailureSnapshot() {
  try {
    window.sessionStorage.removeItem(CHAT_GENERATION_FAILURE_STORAGE_KEY);
  } catch {
    // Ignore storage failures; a fresh chat can still reset in memory.
  }
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

function generationProgressFromJob(job: GenerationJob): number {
  const progressValue = job.progress?.progress_percent ?? job.progress_percent;
  if (typeof progressValue === "number" && Number.isFinite(progressValue)) {
    return Math.max(12, Math.min(100, Math.round(progressValue)));
  }
  if (job.status === "done" || job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
    return 100;
  }
  if (job.status === "running" || job.status === "t2i_running" || job.status === "rendering") {
    return 68;
  }
  return 24;
}

function buildGenerationJobUserInput(state: ChatFlowState) {
  return state.userInput;
}

function buildGenerationJobBriefMetadata(state: ChatFlowState) {
  const brief = buildBrief(state);
  return {
    purpose: brief.purpose,
    item: brief.item,
    copy: brief.copy,
    tone: brief.tone,
    channel: brief.channel,
    image_direction: brief.imageDirection
  };
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
  const context = asRecord(payload.context ?? payload.inferred_context ?? metadata.context);
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

  const copyCandidates = getPayloadArray(payload, "copyCandidates", "copy_candidates");
  if (copyCandidates.length > 0 || payload.type === "copy_candidates") {
    return {
      type: "copy_candidates",
      jobId: job.job_id,
      threadId,
      status: job.status,
      context: normalizeInferredContext(context),
      copyCandidates: copyCandidates as never[],
      recommendedCopyId: getPayloadString(payload, "recommendedCopyId", "recommended_copy_id"),
      copyGenerationMode: fallbackCopyGenerationMode
    };
  }

  return {
    type: "brief_ready",
    jobId: job.job_id,
    threadId,
    status: job.status,
    context: context as InferredContext,
    brief: asRecord(payload.brief ?? payload.final_brief) as ChatBrief,
    copyGenerationMode: fallbackCopyGenerationMode ?? "no_copy"
  };
}

type PhotoGenerateInput = {
  file: File;
  prompt: string;
} & GenerationStartOptions;

export function ChatGenerateClient({ initialSurface = "home", initialStage = "start" }: ChatGenerateClientProps) {
  const router = useRouter();
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);
  const [optimisticSurface, setOptimisticSurface] = useState<DashboardSurface | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [generationProgress, setGenerationProgress] = useState(0);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [generatedCreatives, setGeneratedCreatives] = useState<MockCreative[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [isCurrentThreadDeleteOpen, setCurrentThreadDeleteOpen] = useState(false);
  const [isDeletingCurrentThread, setDeletingCurrentThread] = useState(false);
  const [currentThreadDeleteError, setCurrentThreadDeleteError] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const jobIdParam = searchParams?.get("jobId");
  const threadIdParam = searchParams?.get("threadId");
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);
  const activeThreadRef = useRef({ threadId: "", conversationMessageCount: 0 });
  const appSurface = optimisticSurface ?? initialSurface;
  const currentGenerationJobInterrupt = getPendingGenerationJobParsedInterrupt(state.generationJob);

  const showArchiveStoragePendingToast = useCallback((title: string) => {
    showToast(`${title} 저장은 실제 보관함 연결 후 사용할 수 있어요.`);
  }, []);

  const navigateTo = useCallback(
    (surface: DashboardSurface, stage?: DashboardStage) => {
      setOptimisticSurface(surface);
      router.push(buildDashboardHref(surface, stage));
    },
    [router]
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
    setGenerationProgress(stage === "generating" ? 68 : stage === "start" ? 0 : 100);
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
      setGenerationProgress(100);
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
      copyGenerationMode: response.copyGenerationMode,
      imageGenerationEngine: imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
      sourceImagePath: sourceImagePath ?? null,
      referenceImagePath: referenceImagePath ?? null,
      userCustomHeadline: userCustomHeadline ?? null,
      userCustomSubcopy: userCustomSubcopy ?? null
    });
  }, [applyBriefReadyResponse]);

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
      return;
    }

    let isActive = true;
    const sessionCreatives = readGeneratedCreatives();
    setGeneratedCreatives(sessionCreatives);

    void listArchiveItems({ limit: 50 })
      .then((response) => {
        if (!isActive) {
          return;
        }

        const archivedCreatives = response.items
          .map(archiveItemToCreative)
          .filter((creative): creative is MockCreative => Boolean(creative));

        setGeneratedCreatives(archivedCreatives.length > 0 ? archivedCreatives : sessionCreatives);
      })
      .catch(() => {
        if (isActive) {
          setGeneratedCreatives(sessionCreatives);
        }
      });

    return () => {
      isActive = false;
    };
  }, [appSurface]);

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

          if (restoreState) {
            dispatch({
              type: "restoreThreadSnapshot",
              ...restoreState,
              generationJob: job,
              conversationMessages: transcript.length > 0 ? transcript : restoreState.conversationMessages
            });
          } else {
            dispatch({ type: "showResultShell" });
            dispatch({ type: "generationJobUpdated", generationJob: job });
          }

          clearGenerationFailureSnapshot();
          setShowHistory(false);
          setGenerationProgress(generationProgressFromJob(job));

          if (job.status === "waiting_user_input" && restoreState?.currentQuestion) {
            setGenerationStage("jobQuestion");
            lastPrimedStageRef.current = "generating";
            return;
          }

          if (isTerminalGenerationJobStatus(job.status)) {
            setGenerationStage("complete");
            lastPrimedStageRef.current = "complete";
            return;
          }

          setGenerationStage("generating");
          lastPrimedStageRef.current = "generating";
          void pollGenerationJobUntilDoneOrQuestion(job);
        })
        .catch(() => {
          if (!isActive) {
            return;
          }
          const failure = readGenerationFailureSnapshot();
          if (failure) {
            dispatch({ type: "showGenerationFailure", ...failure });
            setGenerationProgress(100);
            setGenerationStage("complete");
            lastPrimedStageRef.current = "complete";
            return;
          }
          dispatch({ type: "showGenerationFailure", message: "생성 요청 상태를 불러오지 못했어요. 잠시 후 다시 시도해주세요." });
          setGenerationProgress(100);
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
        setGenerationProgress(restoreState.currentQuestion ? 65 : 80);
        setGenerationStage(restoreState.currentQuestion ? "jobQuestion" : "brief");
        lastPrimedStageRef.current = restoreState.currentQuestion ? "generating" : "brief";
      }).catch(() => {
        showToast("대화 기록을 불러오는데 실패했습니다.");
      });
      return;
    }

    if (initialStage === "start") {
      const snapshot = readChatFlowSnapshot();
      if (snapshot) {
        clearChatTurnSnapshot();
        restoreBriefSnapshot(snapshot, "start");
        return;
      }

      const pendingTurn = readChatTurnSnapshot();
      if (pendingTurn) {
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
        applyTurnResponse(
          pendingTurn.prompt,
          pendingTurn.response,
          pendingTurn.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE,
          pendingTurn.sourceImagePath ?? null,
          pendingTurn.referenceImagePath ?? null,
          pendingTurn.userCustomHeadline ?? null,
          pendingTurn.userCustomSubcopy ?? null
        );
        setGenerationProgress(0);
        setGenerationStage("brief");
        lastPrimedStageRef.current = "start";
        return;
      }

      if (lastPrimedStageRef.current === "start") {
        return;
      }
      clearChatFlowSnapshot();
      clearChatTurnSnapshot();
      dispatch({ type: "reset" });
      setGenerationProgress(0);
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
      setGenerationProgress(100);
      setGenerationStage("complete");
      lastPrimedStageRef.current = initialStage;
      return;
    }

    dispatch({ type: "reset" });
    dispatch({ type: "showResultShell" });
    setGenerationProgress(0);
    setGenerationStage("complete");
    lastPrimedStageRef.current = initialStage;
  }, [appSurface, applyTurnResponse, initialStage, jobIdParam, restoreBriefSnapshot, threadIdParam]);

  useEffect(() => {
    if (generationStage !== "browsing") {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setGenerationProgress((current) => Math.min(current + 3, 92));
    }, 650);

    return () => window.clearInterval(timer);
  }, [generationStage]);

  async function handleSubmitPrompt(prompt: string, options: GenerationStartOptions = {}) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    const selectedReferenceTemplateId = (options.selectedReferenceTemplateId ?? readGenerationDraftReferenceTemplateId()) || undefined;
    const requestContext = readGenerationRequestContext();
    const imageGenerationEngine = options.imageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE;
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
        adFormat: options.adFormat ?? "instagram_feed",
        runMode: "graph_job",
        copyGenerationMode: options.copyGenerationMode ?? undefined,
        selectedReferenceTemplateId: selectedReferenceTemplateId ?? undefined,
        referenceImagePath,
        userCustomHeadline: options.userCustomHeadline ?? undefined,
        userCustomSubcopy: options.userCustomSubcopy ?? undefined
      });

      const turnResponse = generationJobToChatTurnResponse(response.job, options.copyGenerationMode);
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
      if (selectedReferenceTemplateId) {
        writeGenerationDraftReferenceTemplateId(selectedReferenceTemplateId);
      }
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "생성 요청에 실패했습니다. 잠시 후 다시 시도해주세요."
      });
    }
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
        const turnResponse = generationJobToChatTurnResponse(response.job, state.copyGenerationMode);
        applyTurnResponse(
          state.userInput,
          turnResponse,
          state.selectedImageGenerationEngine,
          state.sourceImagePath ?? null,
          state.referenceImagePath ?? null,
          state.userCustomHeadline,
          state.userCustomSubcopy
        );
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
        message: error instanceof Error ? error.message : "답변 전송에 실패해 다시 시도해주세요."
      });
    }
  }

  async function handleStartPhotoGeneration(input: PhotoGenerateInput) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    setGenerationProgress(0);
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

  async function handleContinueToBrief() {
    if (!state.jobId || !state.threadId) {
      dispatch({
        type: "backendRequestFailed",
        message: "생성 연결 정보가 없어 실제 이미지 생성을 시작할 수 없습니다. 첫 요청을 다시 보내주세요."
      });
      return;
    }

    dispatch({ type: "beginBriefRequest" });
    try {
      const response = await createChatBrief({
        jobId: state.jobId,
        threadId: state.threadId,
        selectedCopyId: state.selectedCopyId,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone,
        customDirection: state.customDirection
      });
      const snapshot = {
        prompt: state.userInput,
        jobId: state.jobId,
        threadId: state.threadId,
        context: state.inferredContext,
        copyCandidates: state.copyCandidates,
        copyCandidateSource: state.copyCandidateSource,
        selectedCopyId: state.selectedCopyId,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone,
        customDirection: state.customDirection,
        userCustomHeadline: state.userCustomHeadline,
        userCustomSubcopy: state.userCustomSubcopy,
        brief: response.brief,
        selectedReferenceTemplateId: state.selectedReferenceTemplateId,
        selectedReferenceTemplateTitle: state.selectedReferenceTemplateTitle,
        imageGenerationEngine: state.selectedImageGenerationEngine,
        sourceImagePath: state.sourceImagePath ?? null,
        referenceImagePath: state.referenceImagePath ?? null
      };
      writeChatFlowSnapshot(snapshot);
      clearChatTurnSnapshot();
      setGeneratedCreatives(response.brief.finalImagePath ? addGeneratedCreativeSnapshot(snapshot) : readGeneratedCreatives());
      dispatch({ type: "backendBriefSucceeded", brief: response.brief });
      dispatch({ type: "continueToBrief" });
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "브리프와 이미지 생성에 실패했습니다. 설정을 확인한 뒤 다시 시도해주세요."
      });
    }
  }

  function stopForGenerationJobInterrupt(job: GenerationJob): boolean {
    const interrupt = getPendingGenerationJobParsedInterrupt(job);
    if (!interrupt) {
      return false;
    }

    if (interrupt.type === "option_question") {
      dispatch({ type: "generationJobQuestionReceived", generationJob: job, question: interrupt.optionQuestion });
    } else {
      dispatch({ type: "generationJobInterruptReceived", generationJob: job });
    }
    setGenerationProgress(generationProgressFromJob(job));
    setGenerationStage("jobQuestion");
    lastPrimedStageRef.current = "generating";
    setOptimisticSurface("chat");
    router.push(buildChatStageHrefForJob("generating", job));
    return true;
  }

  async function pollGenerationJobUntilDoneOrQuestion(initialJob: GenerationJob): Promise<GenerationJob> {
    let currentJob = initialJob;
    dispatch({ type: "generationJobUpdated", generationJob: currentJob });
    setGenerationProgress(generationProgressFromJob(currentJob));

    if (stopForGenerationJobInterrupt(currentJob)) {
      return currentJob;
    }

    for (let attempt = 0; attempt < GENERATION_JOB_MAX_POLLS && !isTerminalGenerationJobStatus(currentJob.status); attempt += 1) {
      await delay(GENERATION_JOB_POLL_INTERVAL_MS);
      const response = await getGenerationJob(currentJob.job_id);
      currentJob = response.job;
      dispatch({ type: "generationJobUpdated", generationJob: currentJob });
      setGenerationProgress(generationProgressFromJob(currentJob));

      if (stopForGenerationJobInterrupt(currentJob)) {
        return currentJob;
      }
    }

    if (currentJob.status === "waiting_user_input") {
      throw new Error("추가 질문 정보를 받지 못했어요. 잠시 후 다시 시도해주세요.");
    }

    setGenerationProgress(generationProgressFromJob(currentJob));
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
    setGenerationStage("generating");
    setGenerationProgress((current) => Math.max(current, 52));

    try {
      const answerPayload = {
        field: question.field,
        value: input.value,
        displayText: input.label,
        ...(input.customText ? { customText: input.customText } : {})
      };
      const response = await answerGenerationJob(jobId, answerPayload);
      await pollGenerationJobUntilDoneOrQuestion(response.job);
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
    setGenerationStage("generating");
    setGenerationProgress((current) => Math.max(current, 52));

    try {
      const response = await answerGenerationJob(jobId, { selectedCopyId: input.selectedCopyId, displayText: input.label });
      await pollGenerationJobUntilDoneOrQuestion(response.job);
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
    setGenerationStage("generating");
    setGenerationProgress((current) => Math.max(current, 52));

    try {
      const response = await answerGenerationJob(jobId, {
        displayText: input.label,
        userCustomHeadline: input.userCustomHeadline,
        ...(input.userCustomSubcopy ? { userCustomSubcopy: input.userCustomSubcopy } : {})
      });
      await pollGenerationJobUntilDoneOrQuestion(response.job);
    } catch (error) {
      dispatch({
        type: "generationJobFailed",
        message: error instanceof Error ? error.message : "입력한 문구를 보내지 못했어요. 잠시 후 다시 시도해주세요."
      });
      setGenerationStage("jobQuestion");
    }
  }

  async function handleOpenGeneratedResult() {
    const engine = state.selectedImageGenerationEngine ?? DEFAULT_IMAGE_GENERATION_ENGINE;
    const engineOption = getGenerationEngineOption(engine);
    const backendEngine = resolveGenerationEnginePreference(engine);
    const selectedReferenceTemplateId = state.selectedReferenceTemplateId || readGenerationDraftReferenceTemplateId() || undefined;
    const sourceImagePath = state.sourceImagePath || undefined;
    const referenceImagePath = state.referenceImagePath || undefined;
    const requestUserInput = appendSavedBrandKitContext(buildGenerationJobUserInput(state));

    clearGenerationFailureSnapshot();
    dispatch({ type: "generationJobRequested" });
    setGenerationProgress(18);
    setGenerationStage("generating");
    lastPrimedStageRef.current = "generating";
    navigateTo("chat", "generating");

    try {
      const created = await createGenerationJob({
        userInput: requestUserInput,
        threadId: toGenerationJobThreadId(state.threadId),
        entryMode: state.entryMode,
        copyGenerationMode: state.copyGenerationMode,
        adFormat: state.selectedChannelId,
        runMode: resolveGenerationRunMode(engine),
        selectedReferenceTemplateId,
        sourceImagePath,
        referenceImagePath,
        selectedCopyId: state.selectedCopyId || undefined,
        selectedChannelId: state.selectedChannelId,
        selectedTone: state.selectedTone || undefined,
        customDirection: state.customDirection,
        userCustomHeadline: state.userCustomHeadline || undefined,
        userCustomSubcopy: state.userCustomSubcopy || undefined,
        metadata: {
          source: "web_generation_flow",
          source_image_path: sourceImagePath ?? null,
          reference_image_path: referenceImagePath ?? null,
          selected_engine: engine,
          requested_engine: backendEngine,
          t2i_engine: backendEngine,
          selected_engine_label: engineOption.modelName,
          selected_copy_id: state.selectedCopyId || null,
          selected_channel_id: state.selectedChannelId,
          selected_tone: state.selectedTone || null,
          reference_template_title: state.selectedReferenceTemplateTitle || null,
          final_brief: buildGenerationJobBriefMetadata(state)
        }
      });

      setOptimisticSurface("chat");
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
      setGenerationProgress(100);
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
    setGenerationProgress(0);
    setGenerationStage("brief");
    navigateTo("chat", "start");
  }

  function handleUseReferenceTemplate(template: ReferenceTemplateCard) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationFailureSnapshot();
    dispatch({ type: "reset" });
    setGenerationProgress(0);
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
      setGenerationProgress(0);
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

  async function handleDeleteGeneratedAd(creativeId: string, title: string) {
    if (creativeId.startsWith("generated-")) {
      setGeneratedCreatives(removeGeneratedCreative(creativeId));
      showToast(`${title} 항목을 보관함에서 삭제했어요.`);
      return;
    }

    try {
      await deleteArchiveItem(creativeId);
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

  return (
    <MobileShell>
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
            setOptimisticSurface("chat");
            router.push(`/generate/chat?threadId=${threadId}`);
          }}
        />
      ) : null}

      {appSurface === "reference" ? (
        <ReferenceBrowseStep
          state={state}
          progress={generationProgress}
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
          onOpenNotifications={() => router.push(buildNotificationHref())}
        />
      ) : null}

      {appSurface === "my" || appSurface === "brand" ? (
        <MyPageStep />
      ) : null}

      {appSurface === "photo" ? (
        <PhotoGenerateStep
          onBack={() => router.back()}
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
            router.push(`/generate/chat?threadId=${threadId}`);
            setShowHistory(false);
          }}
        />
      ) : appSurface === "chat" && state.step === 1 ? (
        <ChatStartStep
          onSubmit={handleSubmitPrompt}
          onBack={() => router.back()}
          onGoHome={() => navigateTo("home")}
          onHistory={() => setShowHistory(true)}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onAnswer={handleAnswerQuestion}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && !state.currentQuestion ? (
        <IntentReviewStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectTone={(tone) => dispatch({ type: "selectTone", tone })}
          onContinue={() => dispatch({ type: "continueToCopy" })}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 3 ? (
        <CopyChannelStep
          state={state}
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
          state={state}
          onBack={handleBackFromBrief}
          onGenerate={handleOpenGeneratedResult}
          onDelete={state.threadId || threadIdParam ? handleRequestCurrentThreadDelete : undefined}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "jobQuestion" && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={state}
          onBack={() => setGenerationStage("brief")}
          onAnswer={handleAnswerGenerationJobQuestion}
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
          isLoading={state.isLoading}
          errorMessage={state.errorMessage}
          onBack={() => setGenerationStage("brief")}
          onSelectCopyCandidate={handleSelectGenerationJobCopyCandidate}
          onSubmitCustomCopy={handleSubmitGenerationJobCustomCopy}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "generating" ? (
        <GenerationInProgressStep
          state={state}
          progress={generationProgress}
          onBrowse={() => setGenerationStage("browsing")}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "browsing" ? (
        <ReferenceBrowseStep
          state={state}
          progress={generationProgress}
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
          state={state}
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
          state={state}
          progress={100}
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
