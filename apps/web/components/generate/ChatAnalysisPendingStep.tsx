"use client";

import type { ChatFlowState } from "@/types/marketing";
import { ChatTimelineStep } from "./ChatTimelineStep";
import styles from "./generate.module.css";

type ChatAnalysisPendingStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onDelete?: () => void;
};

export function ChatAnalysisPendingStep({ state, onBack, onDelete }: ChatAnalysisPendingStepProps) {
  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <div className={styles.assistantBubble} aria-live="polite">
        <span className={styles.assistantAvatar}>AI</span>
        <p className={`${styles.bubble} ${styles.loadingHelperText}`}>
          요청을 읽고 있어요. 필요한 정보가 정리되면 바로 이어서 물어볼게요
          <span aria-hidden="true">.</span>
          <span aria-hidden="true">.</span>
          <span aria-hidden="true">.</span>
        </p>
      </div>
    </ChatTimelineStep>
  );
}
