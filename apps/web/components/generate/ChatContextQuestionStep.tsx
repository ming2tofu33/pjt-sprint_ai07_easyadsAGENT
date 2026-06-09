"use client";

import { Send } from "lucide-react";
import { useState } from "react";
import type { ChatFlowState, OptionItem } from "@/types/marketing";
import { AutosizeTextarea } from "./AutosizeTextarea";
import { ChoiceChip } from "./ChoiceChip";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type ChatContextQuestionStepProps = {
  state: ChatFlowState;
  onAnswer: (input: { value: string; label: string; customText?: string }) => void;
  onBack: () => void;
  onDelete?: () => void;
};

export function ChatContextQuestionStep({ state, onAnswer, onBack, onDelete }: ChatContextQuestionStepProps) {
  const [customText, setCustomText] = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [selectedOption, setSelectedOption] = useState<OptionItem | null>(null);
  const question = state.currentQuestion;
  if (!question) {
    return null;
  }

  function submitCustomAnswer() {
    if (state.isLoading) return;
    const answer = customText.trim();
    if (!answer) return;
    onAnswer({ value: "custom", label: answer, customText: answer });
    setCustomText("");
  }

  function submitSelectedOption() {
    if (state.isLoading || !selectedOption) return;
    onAnswer({ value: selectedOption.value, label: selectedOption.label });
  }

  function answerOption(option: OptionItem) {
    if (state.isLoading) return;
    if (option.value === "custom") {
      setShowCustomInput(true);
      setSelectedOption(null);
      return;
    }
    setSelectedOption(option);
    setShowCustomInput(false);
  }

  const noChips = question.options.length === 0;
  const effectiveShowCustomInput = showCustomInput || noChips;

  return (
    <>
      <StepHeader title="AI가 필요한 정보를 물어볼게요" canGoBack onBack={onBack} onDelete={onDelete} />

      <section className={styles.chatTranscript} aria-label="대화 내용">
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

      <section className={styles.contextCard} aria-label="현재까지 파악한 내용">
        <div className={styles.contextTitleGroup}>
          <MascotImage role="questionPaper" decorative className={styles.contextTitleMascot} />
          <h2 className={styles.contextTitle}>현재까지 파악한 내용</h2>
        </div>
        <div className={styles.contextGrid}>
          <div className={styles.contextItem}>
            <span>업종</span>
            <strong>{state.inferredContext.businessType || "확인 필요"}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>상품/서비스</span>
            <strong>{state.inferredContext.itemOrService || "확인 필요"}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>광고 목적</span>
            <strong>{state.inferredContext.promotionGoal || "확인 필요"}</strong>
          </div>
        </div>
      </section>

      <h2 className={styles.sectionTitle}>{question.question}</h2>
      <div className={styles.chipGrid}>
        {question.options.map((option) => (
          <ChoiceChip
            key={`${question.field}-${option.id}`}
            disabled={state.isLoading}
            selected={option.value !== "custom" && selectedOption?.id === option.id}
            onClick={() => answerOption(option)}
          >
            <span>{option.label}</span>
          </ChoiceChip>
        ))}
      </div>

      {effectiveShowCustomInput ? (
        <label className={`${styles.inputCard} ${styles.contextAnswerInputCard}`}>
          <AutosizeTextarea
            className={`${styles.input} ${styles.promptTextarea}`}
            value={customText}
            aria-label="직접 답변 입력"
            placeholder="직접 입력"
            disabled={state.isLoading}
            onChange={(event) => setCustomText(event.target.value)}
            onSubmit={submitCustomAnswer}
          />
          <button className={styles.sendButton} type="button" aria-label="직접 답변 보내기" disabled={state.isLoading} onClick={submitCustomAnswer}>
            <Send size={18} aria-hidden="true" />
          </button>
        </label>
      ) : selectedOption ? (
        <button className={styles.primaryButton} type="button" disabled={state.isLoading} onClick={submitSelectedOption}>
          선택 완료
        </button>
      ) : null}

      {state.errorMessage ? <p className={styles.helperText}>{state.errorMessage}</p> : null}
    </>
  );
}
