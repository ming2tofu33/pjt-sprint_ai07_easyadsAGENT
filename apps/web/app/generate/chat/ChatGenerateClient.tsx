"use client";

import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatContextQuestionStep } from "@/components/generate/ChatContextQuestionStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { DashboardToast } from "@/components/generate/DashboardToast";
import { GenerationCompleteStep } from "@/components/generate/GenerationCompleteStep";
import { GenerationInProgressStep } from "@/components/generate/GenerationInProgressStep";
import { HomeStartStep } from "@/components/generate/HomeStartStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { MyPageStep } from "@/components/generate/MyPageStep";
import { PhotoGenerateStep } from "@/components/generate/PhotoGenerateStep";
import { RecentAdsStep } from "@/components/generate/RecentAdsStep";
import { ReferenceBrowseStep } from "@/components/generate/ReferenceBrowseStep";
import { StudioEntryStep } from "@/components/generate/StudioEntryStep";
import {
  answerChatQuestion,
  createChatBrief,
  startChatGeneration,
  startPhotoGeneration,
  uploadPhotoAsset,
  type ChatTurnResponse
} from "@/lib/api-client";
import { buildAdHref } from "@/lib/ad-navigation";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";
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
import {
  appendSavedBrandKitContext,
  clearGenerationDraftPrompt
} from "@/lib/generation-request-context";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { buildReferenceStyleHref } from "@/lib/reference-navigation";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import type { ChatBrief, CopyGenerationMode, InferredContext } from "@/types/marketing";

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing";

type ChatGenerateClientProps = {
  initialSurface?: DashboardSurface;
  initialStage?: DashboardStage;
};

type ChatFlowSnapshot = GeneratedCreativeSnapshot;
type ChatTurnSnapshot = {
  prompt: string;
  response: ChatTurnResponse;
};

const CHAT_FLOW_SNAPSHOT_STORAGE_KEY = "easyads_chat_flow_snapshot_v1";
const CHAT_TURN_SNAPSHOT_STORAGE_KEY = "easyads_chat_turn_snapshot_v1";

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

function isQuestionResponse(response: ChatTurnResponse): response is Extract<ChatTurnResponse, { type: "option_question" }> {
  return response.type === "option_question";
}

function isBriefReadyResponse(response: ChatTurnResponse): response is Extract<ChatTurnResponse, { type: "brief_ready" }> {
  return response.type === "brief_ready";
}

type PhotoGenerateInput = {
  file: File;
  prompt: string;
  copyGenerationMode?: CopyGenerationMode;
};

export function ChatGenerateClient({ initialSurface = "home", initialStage = "start" }: ChatGenerateClientProps) {
  const router = useRouter();
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);
  const [optimisticSurface, setOptimisticSurface] = useState<DashboardSurface | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [generationProgress, setGenerationProgress] = useState(0);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [generatedCreatives, setGeneratedCreatives] = useState<MockCreative[]>([]);
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);
  const appSurface = optimisticSurface ?? initialSurface;

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
      copyCandidateSource: snapshot.copyCandidateSource
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
        brief: response.brief
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
        copyGenerationMode: response.copyGenerationMode ?? "no_copy"
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

  const applyTurnResponse = useCallback((prompt: string, response: ChatTurnResponse) => {
    if (isQuestionResponse(response)) {
      dispatch({
        type: "backendQuestionReceived",
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        question: response.question
      });
      return;
    }
    if (isBriefReadyResponse(response)) {
      applyBriefReadyResponse(prompt, response);
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
      copyGenerationMode: response.copyGenerationMode
    });
  }, [applyBriefReadyResponse]);

  useEffect(() => {
    setOptimisticSurface(null);
  }, [initialSurface]);

  useEffect(() => {
    if (appSurface === "ads") {
      setGeneratedCreatives(readGeneratedCreatives());
    }
  }, [appSurface]);

  useEffect(() => {
    if (appSurface !== "chat") {
      lastPrimedStageRef.current = null;
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
        dispatch({ type: "submitPrompt", prompt: pendingTurn.prompt });
        applyTurnResponse(pendingTurn.prompt, pendingTurn.response);
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

    dispatch({ type: "reset" });
    dispatch({ type: "showResultShell" });
    setGenerationProgress(0);
    setGenerationStage("complete");
    lastPrimedStageRef.current = initialStage;
  }, [appSurface, applyTurnResponse, initialStage, restoreBriefSnapshot]);

  useEffect(() => {
    if (generationStage !== "generating" && generationStage !== "browsing") {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setGenerationProgress((current) => {
        const nextProgress = Math.min(current + 8, 100);
        if (nextProgress >= 100) {
          window.clearInterval(timer);
          setGenerationStage("complete");
          lastPrimedStageRef.current = "complete";
          navigateTo("chat", "complete");
        }
        return nextProgress;
      });
    }, 650);

    return () => window.clearInterval(timer);
  }, [generationStage, navigateTo]);

  async function handleSubmitPrompt(prompt: string, options: { copyGenerationMode?: CopyGenerationMode } = {}) {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    dispatch({ type: "submitPrompt", prompt, copyGenerationMode: options.copyGenerationMode });
    try {
      const response = await startChatGeneration(appendSavedBrandKitContext(prompt), {
        copyGenerationMode: options.copyGenerationMode
      });
      applyTurnResponse(prompt, response);
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "백엔드 연결에 실패했습니다. 잠시 후 다시 시도해주세요."
      });
    }
  }

  async function handleAnswerQuestion(input: { value: string; label: string; customText?: string }) {
    if (!state.currentQuestion || !state.jobId || !state.threadId) {
      return;
    }

    dispatch({ type: "submitQuestionAnswer", label: input.label });
    try {
      const response = await answerChatQuestion({
        jobId: state.jobId,
        threadId: state.threadId,
        field: state.currentQuestion.field,
        value: input.value,
        customText: input.customText
      });
      applyTurnResponse(state.userInput, response);
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
    setGenerationProgress(0);
    setGenerationStage("brief");

    try {
      const upload = await uploadPhotoAsset(input.file);
      const response = await startPhotoGeneration({
        userInput: appendSavedBrandKitContext(input.prompt),
        sourceImagePath: upload.sourceImagePath,
        copyGenerationMode: input.copyGenerationMode
      });
      writeChatTurnSnapshot({ prompt: input.prompt, response });
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
        message: "백엔드 세션이 없어 실제 이미지 생성을 시작할 수 없습니다. 첫 요청을 다시 보내주세요."
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
        brief: response.brief
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

  function handleOpenGeneratedResult() {
    setGenerationProgress(100);
    setGenerationStage("complete");
    lastPrimedStageRef.current = "complete";
    navigateTo("chat", "complete");
  }

  function handleOpenFreshChat() {
    clearChatFlowSnapshot();
    clearChatTurnSnapshot();
    clearGenerationDraftPrompt();
    dispatch({ type: "reset" });
    setGenerationProgress(0);
    setGenerationStage("brief");
    navigateTo("chat", "start");
  }

  function handleRegenerateFromRecent() {
    showToast("새 요청 화면에서 비슷하게 만들 광고를 입력해주세요.");
    handleOpenFreshChat();
  }

  function handleDeleteGeneratedAd(creativeId: string, title: string) {
    setGeneratedCreatives(removeGeneratedCreative(creativeId));
    showToast(`${title} 항목을 보관함에서 삭제했어요.`);
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
          onShowProgress={() => navigateTo("studio")}
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
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
          onShowProgress={() => showToast("광고 생성 상태를 확인합니다.")}
          onOpenGeneratedAd={() => navigateTo("chat", "complete")}
          onOpenAd={(creativeId) => router.push(buildAdHref(creativeId))}
          onDeleteGeneratedAd={handleDeleteGeneratedAd}
          onDeleteSampleAd={(title) => showToast(`${title} 항목을 보관함에서 삭제했어요.`)}
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

      {appSurface === "chat" && state.step === 1 ? (
        <ChatStartStep onSubmit={handleSubmitPrompt} onBack={() => router.back()} onGoHome={() => navigateTo("home")} />
      ) : null}

      {appSurface === "chat" && state.step === 2 && state.currentQuestion ? (
        <ChatContextQuestionStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onAnswer={handleAnswerQuestion}
        />
      ) : null}

      {appSurface === "chat" && state.step === 2 && !state.currentQuestion ? (
        <IntentReviewStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectTone={(tone) => dispatch({ type: "selectTone", tone })}
          onContinue={() => dispatch({ type: "continueToCopy" })}
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
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "brief" ? (
        <BriefConfirmStep state={state} onBack={handleBackFromBrief} onGenerate={handleOpenGeneratedResult} />
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
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
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
          onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
          onEditCreative={() => showToast("선택한 시안 편집 화면은 곧 연결됩니다.")}
          onSaveSelected={() => navigateTo("ads")}
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
          onOpenCreative={(creativeId) => router.push(buildReferenceStyleHref(creativeId))}
          onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
        />
      ) : null}
      <DashboardToast message={toastMessage} />
    </MobileShell>
  );
}
