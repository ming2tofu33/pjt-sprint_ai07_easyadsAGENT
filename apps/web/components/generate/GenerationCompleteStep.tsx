"use client";

import { Bookmark, CheckCircle2, Sparkles } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
};

const mockCreatives = [
  { label: "봄을 닮은 한 잔", tone: "pink" },
  { label: "New Strawberry Latte", tone: "coral" },
  { label: "딸기 한가득 오늘의 신메뉴", tone: "cream" },
  { label: "STRAWBERRY LATTE", tone: "mint" }
];

export function GenerationCompleteStep({ state, onBrowseSimilar }: GenerationCompleteStepProps) {
  const brief = buildBrief(state);

  return (
    <>
      <StepHeader title="생성 완료" />

      <section className={styles.completeHero}>
        <span>
          <CheckCircle2 size={28} aria-hidden="true" />
        </span>
        <h1>찰떡 광고 시안이 완성됐어요</h1>
        <p>{brief.item} 광고 시안 4개가 준비됐어요.</p>
      </section>

      <section className={styles.resultGrid} aria-label="생성된 광고 시안">
        {mockCreatives.map((creative) => (
          <article className={`${styles.resultCard} ${styles[`referenceTone${creative.tone}`]}`} key={creative.label}>
            <button aria-label={`${creative.label} 저장`} type="button">
              <Bookmark size={14} aria-hidden="true" />
            </button>
            <div className={styles.mockCup}>
              <span />
            </div>
            <h2>{creative.label}</h2>
            <p>{brief.copy}</p>
          </article>
        ))}
      </section>

      <p className={styles.savedNotice}>
        <CheckCircle2 size={18} aria-hidden="true" />
        생성된 광고는 내 광고 보관함에 자동 저장됐어요.
      </p>

      <div className={styles.stepFooter}>
        <button className={styles.primaryButton} type="button">
          결과 확인하기 <Sparkles size={18} aria-hidden="true" />
        </button>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button">
            내 광고 보관함 보기
          </button>
          <button className={styles.secondaryButton} type="button" onClick={onBrowseSimilar}>
            비슷한 스타일 더 보기
          </button>
        </div>
      </div>
    </>
  );
}
