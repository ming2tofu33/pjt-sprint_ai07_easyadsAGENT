"use client";

import { Diamond, Heart, Leaf, Smile, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { toneOptions } from "@/lib/chat-flow";
import { ChoiceChip } from "./ChoiceChip";
import { StepHeader } from "./StepHeader";
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
};

export function IntentReviewStep({ state, onSelectTone, onContinue, onBack }: IntentReviewStepProps) {
  return (
    <>
      <StepHeader title="AI가 이렇게 이해했어요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>좋아요! 내용을 이해했어요. 제가 파악한 내용은 아래와 같아요.</p>
      </div>

      <section className={styles.contextCard} aria-label="AI가 파악한 내용">
        <h2 className={styles.contextTitle}>파악한 내용</h2>
        <div className={styles.contextGrid}>
          <div className={styles.contextItem}>
            <span>업종</span>
            <strong>{state.inferredContext.businessType}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>상품/서비스</span>
            <strong>{state.inferredContext.itemOrService}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>광고 목적</span>
            <strong>{state.inferredContext.promotionGoal}</strong>
          </div>
        </div>
      </section>

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

      <div className={styles.progressWrap}>
        <span>
          정보 입력 {state.progress.current}/{state.progress.total}
        </span>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: "25%" }} />
        </span>
      </div>

      <button className={styles.primaryButton} type="button" onClick={onContinue}>
        문구 고르기
      </button>
    </>
  );
}
