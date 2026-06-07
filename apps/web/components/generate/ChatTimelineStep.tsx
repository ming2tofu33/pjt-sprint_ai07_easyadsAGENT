"use client";

import type { ReactNode } from "react";
import type { ChatFlowState } from "@/types/marketing";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type ChatTimelineStepProps = {
  state: ChatFlowState;
  children: ReactNode;
  onBack: () => void;
  onDelete?: () => void;
  title?: string;
};

export function ChatTimelineStep({ state, children, onBack, onDelete, title = "대화로 찰떡 만들기" }: ChatTimelineStepProps) {
  return (
    <>
      <StepHeader title={title} canGoBack onBack={onBack} onDelete={onDelete} />

      <section className={`${styles.chatTranscript} ${styles.chatTimelineTranscript}`} aria-label="대화 내용">
        {state.conversationMessages.map((message, index) =>
          message.role === "assistant" ? (
            <div className={styles.assistantBubble} key={`${message.role}-${index}`}>
              <span className={styles.assistantAvatar}>AI</span>
              <p className={styles.bubble}>{message.text}</p>
            </div>
          ) : (
            <p className={styles.userBubble} key={`${message.role}-${index}`}>
              {message.text}
            </p>
          )
        )}
      </section>

      <div className={styles.chatTimelineCards}>{children}</div>
    </>
  );
}
