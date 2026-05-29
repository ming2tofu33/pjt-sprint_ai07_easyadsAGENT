"use client";

import React, { useReducer } from "react";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";

export function ChatGenerateClient() {
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);

  return (
    <MobileShell>
      {state.step === 1 ? (
        <ChatStartStep onSubmit={(prompt) => dispatch({ type: "submitPrompt", prompt })} />
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
          onContinue={() => dispatch({ type: "continueToBrief" })}
        />
      ) : null}

      {state.step === 4 ? <BriefConfirmStep state={state} onBack={() => dispatch({ type: "back" })} /> : null}
    </MobileShell>
  );
}
