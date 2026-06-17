"use client";

import type { ChatFlowState } from "@/types/marketing";
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { WaitingStatusCard } from "./WaitingStatusCard";

type ChatAnalysisPendingStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onDelete?: () => void;
};

export function ChatAnalysisPendingStep({ state, onBack, onDelete }: ChatAnalysisPendingStepProps) {
  const waitingCopy = resolveWaitingStatusCopy({
    state,
    context: state.step >= 4 ? "generation_answer" : "chat_analysis"
  });

  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <WaitingStatusCard copy={waitingCopy} />
    </ChatTimelineStep>
  );
}
