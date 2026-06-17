"use client";

import { Diamond, Heart, Leaf, Smile, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { toneOptions } from "@/lib/chat-flow";
import {
  contextBusinessSummary,
  contextItemLabel,
  contextItemSummary,
  contextPurposeSummary,
} from "@/lib/context-presentation";
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { ChoiceChip } from "./ChoiceChip";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { MascotImage } from "./MascotImage";
import { WaitingStatusCard } from "./WaitingStatusCard";
import styles from "./generate.module.css";

const toneIconMap = {
  heart: Heart,
  leaf: Leaf,
  diamond: Diamond,
  smile: Smile,
  sparkles: Sparkles,
  star: Star
};

type IntentReviewStepProps = {
  state: ChatFlowState;
  onSelectTone: (tone: string) => void;
  onContinue: () => void;
  onBack: () => void;
  onDelete?: () => void;
};

export function IntentReviewStep({ state, onSelectTone, onContinue, onBack, onDelete }: IntentReviewStepProps) {
  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <IntentReviewCard state={state} onSelectTone={onSelectTone} onContinue={onContinue} />
    </ChatTimelineStep>
  );
}

type IntentReviewCardProps = Omit<IntentReviewStepProps, "onBack" | "onDelete">;

export function IntentReviewCard({ state, onSelectTone, onContinue }: IntentReviewCardProps) {
  const hasBackendSession = Boolean(state.jobId && state.threadId);
  const businessSummary = contextBusinessSummary(state.inferredContext) || "확인 필요";
  const itemSummary = contextItemSummary(state.inferredContext) || "확인 필요";
  const purposeSummary = contextPurposeSummary(state.inferredContext) || "확인 필요";
  const itemLabel = contextItemLabel(state.inferredContext);
  const hasBackendContext =
    state.contextSource === "backend" &&
    Boolean(
      state.inferredContext.businessType &&
      (state.inferredContext.itemOrService || state.inferredContext.advertisedSubject) &&
      (state.inferredContext.promotionGoal || state.inferredContext.campaignIntent)
    );
  const cannotContinue = state.isLoading || !hasBackendSession || !hasBackendContext;
  const contextBadge = hasBackendContext ? "요청 분석" : state.isLoading ? "진행 중" : "확인 필요";
  const progressPercent = state.progress.total > 0 ? `${Math.max(0, Math.min(100, (state.progress.current / state.progress.total) * 100))}%` : "0%";
  const waitingCopy = resolveWaitingStatusCopy({ state, context: "chat_analysis" });

  return (
    <>
      <h2 className={styles.timelineSectionTitle}>{state.isLoading ? "요청을 살펴보고 있어요" : "AI가 이렇게 이해했어요"}</h2>

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>
          {state.isLoading
            ? "잠시만요. 요청을 읽고 있어요. 필요한 정보가 정리되면 바로 이어서 물어볼게요."
            : hasBackendContext
              ? "좋아요! 파악한 내용을 아래에 정리했어요."
              : "아직 분석값을 충분히 받지 못했어요. 확인이 필요한 항목을 다시 채워야 해요."}
        </p>
      </div>

      <section className={`${styles.contextCard} ${state.isLoading ? styles.contextCardPending : ""}`} aria-label="AI가 파악한 내용">
        <div className={styles.contextReviewHeader}>
          <div className={styles.contextTitleGroup}>
            <MascotImage role={state.isLoading ? "questionPaper" : "checkPaper"} decorative className={styles.contextTitleMascot} />
            <h2 className={styles.contextTitle}>{state.isLoading ? "차근차근 살펴보는 중" : "파악한 내용"}</h2>
          </div>
          <span>{contextBadge}</span>
        </div>

        {state.isLoading ? (
          <>
            <p className={styles.contextSourceNote}>{waitingCopy.description}</p>
            <WaitingStatusCard copy={waitingCopy} compact />
          </>
        ) : (
          <>
            <p className={styles.contextSourceNote}>
              {hasBackendContext
                ? "아래 값은 이번 요청에 대한 분석 결과입니다."
                : "분석값이 비어 있어 실제 생성 단계로 이동하지 않습니다."}
            </p>
            <div className={styles.contextGrid}>
              <div className={styles.contextItem}>
                <span>업종</span>
                <strong>{businessSummary}</strong>
              </div>
              <div className={styles.contextItem}>
                <span>{itemLabel}</span>
                <strong>{itemSummary}</strong>
              </div>
              <div className={styles.contextItem}>
                <span>광고 목적</span>
                <strong>{purposeSummary}</strong>
              </div>
            </div>
          </>
        )}
      </section>

      {!state.isLoading ? (
        <>
          <div className={styles.assistantBubble}>
            <span className={styles.assistantAvatar}>AI</span>
            <p className={styles.bubble}>더 잘 맞는 광고를 만들기 위해 아래 정보를 조금만 알려주세요.</p>
          </div>

          <h2 className={styles.sectionTitle}>어떤 분위기의 광고가 좋을까요?</h2>
          <div className={styles.chipGrid}>
            {toneOptions.map((tone) => {
              const Icon = toneIconMap[tone.icon];
              return (
                <ChoiceChip
                  key={tone.id}
                  selected={state.selectedTone === tone.label}
                  onClick={() => onSelectTone(tone.label)}
                >
                  <Icon size={16} aria-hidden="true" />
                  <span>{tone.label}</span>
                </ChoiceChip>
              );
            })}
          </div>
        </>
      ) : null}

      <div className={styles.stepFooter}>
        {state.errorMessage ? (
          <p className={styles.helperText}>{state.errorMessage}</p>
        ) : state.isLoading ? (
          <p className={styles.helperText}>{waitingCopy.title}</p>
        ) : !hasBackendSession ? (
          <p className={styles.helperText}>응답을 받은 뒤 문구 선택으로 이동할 수 있어요.</p>
        ) : !hasBackendContext ? (
          <p className={styles.helperText}>분석값이 비어 있어 문구 선택으로 이동할 수 없어요.</p>
        ) : null}
        <div className={styles.progressWrap}>
          <span>
            정보 입력 {state.progress.current}/{state.progress.total}
          </span>
          <span className={styles.progressTrack}>
            <span className={styles.progressBar} style={{ width: progressPercent }} />
          </span>
        </div>

        <button className={styles.primaryButton} type="button" disabled={cannotContinue} onClick={onContinue}>
          {state.isLoading ? "살펴보는 중..." : "문구 고르기"}
        </button>
      </div>
    </>
  );
}
