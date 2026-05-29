"use client";

import React, { useReducer } from "react";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { createChatBrief, startChatGeneration } from "@/lib/api-client";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";

export function ChatGenerateClient() {
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);

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

  return (
    <MobileShell>
      {state.step === 1 ? (
        <ChatStartStep onSubmit={handleSubmitPrompt} />
      ) : null}

      {state.step === 2 ? (
        <IntentReviewStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectTone={(tone) => dispatch({ type: "selectTone", tone })}
          onContinue={() => dispatch({ type: "continueToCopy" })}
        />
      ) : null}

      {state.step === 3 ? (
        <CopyChannelStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectCopy={(copyId) => dispatch({ type: "selectCopy", copyId })}
          onSelectChannel={(channelId) => dispatch({ type: "selectChannel", channelId })}
          onCustomDirection={(value) => dispatch({ type: "setCustomDirection", value })}
          onContinue={handleContinueToBrief}
        />
      ) : null}

      {state.step === 4 ? <BriefConfirmStep state={state} onBack={() => dispatch({ type: "back" })} /> : null}
    </MobileShell>
  );
}
