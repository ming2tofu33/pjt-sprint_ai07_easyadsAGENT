"use client";

import React, { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { GenerationCompleteStep } from "@/components/generate/GenerationCompleteStep";
import { GenerationInProgressStep } from "@/components/generate/GenerationInProgressStep";
import { BrandKitStep } from "@/components/generate/BrandKitStep";
import { HomeStartStep } from "@/components/generate/HomeStartStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { RecentAdsStep } from "@/components/generate/RecentAdsStep";
import { ReferenceBrowseStep } from "@/components/generate/ReferenceBrowseStep";
import { StudioEntryStep } from "@/components/generate/StudioEntryStep";
import { createChatBrief, startChatGeneration } from "@/lib/api-client";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";
import {
  buildDashboardHref,
  parseDashboardStage,
  parseDashboardSurface,
  type DashboardStage,
  type DashboardSurface
} from "@/lib/dashboard-navigation";

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing";

export function ChatGenerateClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);
  const querySurface = parseDashboardSurface(searchParams.get("surface"));
  const dashboardStage = parseDashboardStage(searchParams.get("stage"));
  const [optimisticSurface, setOptimisticSurface] = useState<DashboardSurface | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [generationProgress, setGenerationProgress] = useState(0);
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);
  const appSurface = optimisticSurface ?? querySurface;

  const navigateTo = useCallback(
    (surface: DashboardSurface, stage?: DashboardStage) => {
      setOptimisticSurface(surface);
      router.push(buildDashboardHref(surface, stage));
    },
    [router]
  );

  useEffect(() => {
    setOptimisticSurface(null);
  }, [querySurface]);

  useEffect(() => {
    if (appSurface !== "chat") {
      lastPrimedStageRef.current = null;
      return;
    }

    if (dashboardStage === "start") {
      if (lastPrimedStageRef.current === "start") {
        return;
      }
      dispatch({ type: "reset" });
      setGenerationProgress(0);
      setGenerationStage("brief");
      lastPrimedStageRef.current = "start";
      return;
    }

    if (lastPrimedStageRef.current === dashboardStage) {
      return;
    }

    dispatch({ type: "reset" });
    dispatch({ type: "submitPrompt", prompt: "삼겹살집 회식 손님 많이 오게 포스터 만들어줘" });
    dispatch({ type: "continueToCopy" });
    dispatch({ type: "continueToBrief" });
    setGenerationProgress(dashboardStage === "generating" ? 68 : 100);
    setGenerationStage(
      dashboardStage === "generating" ? "generating" : dashboardStage === "similar" ? "similarBrowsing" : "complete"
    );
    lastPrimedStageRef.current = dashboardStage;
  }, [appSurface, dashboardStage]);

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
    navigateTo("chat", "brief");
  }

  return (
    <MobileShell>
      {appSurface === "home" ? (
        <HomeStartStep
          onOpenStudio={() => navigateTo("studio")}
          onOpenChat={handleOpenFreshChat}
          onOpenReference={() => navigateTo("reference")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("brand")}
        />
      ) : null}

      {appSurface === "studio" ? (
        <StudioEntryStep
          onGoHome={() => navigateTo("home")}
          onOpenChat={handleOpenFreshChat}
          onOpenReference={() => navigateTo("reference")}
          onOpenRecentAds={() => navigateTo("ads")}
          onOpenBrandKit={() => navigateTo("brand")}
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
          onOpenBrandKit={() => navigateTo("brand")}
          onShowProgress={() => navigateTo("studio")}
        />
      ) : null}

      {appSurface === "ads" ? (
        <RecentAdsStep
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenBrandKit={() => navigateTo("brand")}
          onRegenerate={handleRegenerateFromRecent}
        />
      ) : null}

      {appSurface === "brand" ? (
        <BrandKitStep
          onGoHome={() => navigateTo("home")}
          onOpenReference={() => navigateTo("reference")}
          onOpenStudio={() => navigateTo("studio")}
          onOpenRecentAds={() => navigateTo("ads")}
        />
      ) : null}

      {appSurface === "chat" && state.step === 1 ? (
        <ChatStartStep onSubmit={handleSubmitPrompt} />
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
          onOpenBrandKit={() => navigateTo("brand")}
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
          onOpenBrandKit={() => navigateTo("brand")}
        />
      ) : null}
    </MobileShell>
  );
}
