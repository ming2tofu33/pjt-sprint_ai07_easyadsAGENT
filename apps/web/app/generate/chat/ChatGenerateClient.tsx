"use client";

import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
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
import { createChatBrief, startChatGeneration } from "@/lib/api-client";
import { buildAdHref } from "@/lib/ad-navigation";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";
import {
  buildDashboardHref,
  type DashboardStage,
  type DashboardSurface
} from "@/lib/dashboard-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { buildReferenceStyleHref } from "@/lib/reference-navigation";

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing";

type ChatGenerateClientProps = {
  initialSurface?: DashboardSurface;
  initialStage?: DashboardStage;
};

export function ChatGenerateClient({ initialSurface = "home", initialStage = "start" }: ChatGenerateClientProps) {
  const router = useRouter();
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);
  const [optimisticSurface, setOptimisticSurface] = useState<DashboardSurface | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [generationProgress, setGenerationProgress] = useState(0);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);
  const appSurface = optimisticSurface ?? initialSurface;

  const navigateTo = useCallback(
    (surface: DashboardSurface, stage?: DashboardStage) => {
      setOptimisticSurface(surface);
      router.push(buildDashboardHref(surface, stage));
    },
    [router]
  );

  useEffect(() => {
    setOptimisticSurface(null);
  }, [initialSurface]);

  useEffect(() => {
    if (appSurface !== "chat") {
      lastPrimedStageRef.current = null;
      return;
    }

    if (initialStage === "start") {
      if (lastPrimedStageRef.current === "start") {
        return;
      }
      dispatch({ type: "reset" });
      setGenerationProgress(0);
      setGenerationStage("brief");
      lastPrimedStageRef.current = "start";
      return;
    }

    if (lastPrimedStageRef.current === initialStage) {
      return;
    }

    dispatch({ type: "reset" });
    dispatch({ type: "submitPrompt", prompt: "삼겹살집 회식 손님 많이 오게 포스터 만들어줘" });
    dispatch({ type: "continueToCopy" });
    dispatch({ type: "continueToBrief" });
    setGenerationProgress(initialStage === "generating" ? 68 : 100);
    setGenerationStage(
      initialStage === "generating" ? "generating" : initialStage === "similar" ? "similarBrowsing" : "complete"
    );
    lastPrimedStageRef.current = initialStage;
  }, [appSurface, initialStage]);

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

  async function handleSubmitPrompt(prompt: string) {
    dispatch({ type: "submitPrompt", prompt });
    try {
      const response = await startChatGeneration(prompt);
      dispatch({
        type: "backendStartSucceeded",
        prompt,
        jobId: response.jobId,
        threadId: response.threadId,
        context: response.context,
        copyCandidates: response.copyCandidates,
        recommendedCopyId: response.recommendedCopyId
      });
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "백엔드 연결에 실패해 mock 데이터로 진행합니다."
      });
    }
  }

  async function handleContinueToBrief() {
    if (!state.jobId || !state.threadId) {
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
      dispatch({ type: "backendBriefSucceeded", brief: response.brief });
    } catch (error) {
      dispatch({
        type: "backendRequestFailed",
        message: error instanceof Error ? error.message : "브리프 생성 API 연결에 실패해 mock 데이터로 진행합니다."
      });
    } finally {
      dispatch({ type: "continueToBrief" });
    }
  }

  function handleStartMockGeneration() {
    setGenerationProgress(12);
    setGenerationStage("generating");
    lastPrimedStageRef.current = "generating";
    navigateTo("chat", "generating");
  }

  function handleOpenFreshChat() {
    dispatch({ type: "reset" });
    setGenerationProgress(0);
    setGenerationStage("brief");
    navigateTo("chat", "start");
  }

  function handleRegenerateFromRecent() {
    dispatch({ type: "reset" });
    dispatch({ type: "submitPrompt", prompt: "딸기라떼 신메뉴 광고 비슷하게 다시 만들어줘" });
    dispatch({ type: "continueToCopy" });
    dispatch({ type: "continueToBrief" });
    setGenerationProgress(12);
    setGenerationStage("generating");
    lastPrimedStageRef.current = "generating";
    navigateTo("chat", "generating");
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
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenBrandKit={() => navigateTo("my")}
          onRegenerate={handleRegenerateFromRecent}
          onShowProgress={() => showToast("딸기라떼 신메뉴 광고 생성 상태를 확인합니다.")}
          onOpenAd={(creativeId) => router.push(buildAdHref(creativeId))}
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
          onGenerate={() => {
            lastPrimedStageRef.current = "generating";
            navigateTo("chat", "generating");
          }}
        />
      ) : null}

      {appSurface === "chat" && state.step === 1 ? (
        <ChatStartStep onSubmit={handleSubmitPrompt} onBack={() => router.back()} onGoHome={() => navigateTo("home")} />
      ) : null}

      {appSurface === "chat" && state.step === 2 ? (
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
        <BriefConfirmStep state={state} onBack={handleBackFromBrief} onGenerate={handleStartMockGeneration} />
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
            setGenerationProgress(12);
            setGenerationStage("generating");
            lastPrimedStageRef.current = "generating";
            navigateTo("chat", "generating");
          }}
          onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
          onEditCreative={() => showToast("선택한 시안 편집 화면은 곧 연결됩니다.")}
          onOpenCreative={(creativeId) => router.push(buildAdHref(creativeId))}
          onSaveSelected={(creativeId) => router.push(buildAdHref(creativeId, "save"))}
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
