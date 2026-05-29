"use client";

import React, { useEffect, useReducer, useState } from "react";
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

type GenerationStage = "brief" | "generating" | "browsing" | "complete" | "similarBrowsing";
type AppSurface = "home" | "studio" | "chat" | "referenceGallery" | "recentAds" | "brandKit";

export function ChatGenerateClient() {
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);
  const [appSurface, setAppSurface] = useState<AppSurface>("home");
  const [generationStage, setGenerationStage] = useState<GenerationStage>("brief");
  const [generationProgress, setGenerationProgress] = useState(0);

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
        }
        return nextProgress;
      });
    }, 650);

    return () => window.clearInterval(timer);
  }, [generationStage]);

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
  }

  function handleOpenFreshChat() {
    dispatch({ type: "reset" });
    setGenerationProgress(0);
    setGenerationStage("brief");
    setAppSurface("chat");
  }

  function handleRegenerateFromRecent() {
    dispatch({ type: "reset" });
    dispatch({ type: "submitPrompt", prompt: "딸기라떼 신메뉴 광고 비슷하게 다시 만들어줘" });
    dispatch({ type: "continueToCopy" });
    dispatch({ type: "continueToBrief" });
    setGenerationProgress(12);
    setGenerationStage("generating");
    setAppSurface("chat");
  }

  function handleBackFromBrief() {
    setGenerationStage("brief");
    dispatch({ type: "back" });
  }

  return (
    <MobileShell>
      {appSurface === "home" ? (
        <HomeStartStep
          onOpenStudio={() => setAppSurface("studio")}
          onOpenChat={handleOpenFreshChat}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
        />
      ) : null}

      {appSurface === "studio" ? (
        <StudioEntryStep
          onGoHome={() => setAppSurface("home")}
          onOpenChat={handleOpenFreshChat}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
        />
      ) : null}

      {appSurface === "referenceGallery" ? (
        <ReferenceBrowseStep
          state={state}
          progress={generationProgress}
          isStandaloneGallery
          onGoHome={() => setAppSurface("home")}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenStudio={() => setAppSurface("studio")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
          onShowProgress={() => setAppSurface("studio")}
        />
      ) : null}

      {appSurface === "recentAds" ? (
        <RecentAdsStep
          onGoHome={() => setAppSurface("home")}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenStudio={() => setAppSurface("studio")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
          onRegenerate={handleRegenerateFromRecent}
        />
      ) : null}

      {appSurface === "brandKit" ? (
        <BrandKitStep
          onGoHome={() => setAppSurface("home")}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenStudio={() => setAppSurface("studio")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
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
          onGoHome={() => setAppSurface("home")}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenStudio={() => setAppSurface("studio")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "complete" ? (
        <GenerationCompleteStep
          state={state}
          onBrowseSimilar={() => setGenerationStage("similarBrowsing")}
          onGoHome={() => setAppSurface("home")}
          onRegenerate={() => {
            setGenerationProgress(12);
            setGenerationStage("generating");
          }}
        />
      ) : null}

      {appSurface === "chat" && state.step === 4 && generationStage === "similarBrowsing" ? (
        <ReferenceBrowseStep
          state={state}
          progress={100}
          isGenerationComplete
          onShowProgress={() => setGenerationStage("complete")}
          onGoHome={() => setAppSurface("home")}
          onOpenReference={() => setAppSurface("referenceGallery")}
          onOpenStudio={() => setAppSurface("studio")}
          onOpenRecentAds={() => setAppSurface("recentAds")}
          onOpenBrandKit={() => setAppSurface("brandKit")}
        />
      ) : null}
    </MobileShell>
  );
}
