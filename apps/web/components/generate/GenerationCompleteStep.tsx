"use client";

import { Bookmark, CheckCircle2, Download, Home, RotateCcw, Share2, Sparkles } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
  onGoHome: () => void;
  onRegenerate: () => void;
};

const mockCreatives = [
  { label: "봄을 닮은 한 잔", tone: "pink" },
  { label: "New Strawberry Latte", tone: "coral" },
  { label: "딸기 한가득 오늘의 신메뉴", tone: "cream" },
  { label: "STRAWBERRY LATTE", tone: "mint" }
];

const editActions = ["문구 더 짧게", "상품 더 크게", "핑크톤 줄이기", "여백 줄이기", "스토리용 변환", "+ 더보기"];

export function GenerationCompleteStep({ state, onBrowseSimilar, onGoHome, onRegenerate }: GenerationCompleteStepProps) {
  const brief = buildBrief(state);

  return (
    <>
      <StepHeader title="GENERATED RESULTS" canGoBack onBack={onGoHome} />

      <header className={styles.resultsHeader}>
        <h1>찰떡 광고 시안이 완성됐어요</h1>
        <p>마음에 드는 시안을 선택하거나, 수정 요청을 해보세요.</p>
        <div className={styles.resultChips} aria-label="광고 결과 태그">
          <span>카페</span>
          <span>{brief.item}</span>
          <span>신메뉴</span>
          <span>감성적</span>
          <span>{brief.channel.replace(/\s*\(.+\)/, "")}</span>
        </div>
      </header>

      <section className={styles.resultGrid} aria-label="생성된 광고 시안">
        {mockCreatives.map((creative, index) => (
          <article className={`${styles.resultCard} ${styles[`referenceTone${creative.tone}`]}`} key={creative.label}>
            <strong className={styles.resultNumber}>{index + 1}</strong>
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

      <div className={styles.editActionGrid} aria-label="빠른 수정 요청">
        {editActions.map((action) => (
          <button key={action} type="button">
            {action}
          </button>
        ))}
      </div>

      <div className={styles.stepFooter}>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button" onClick={onRegenerate}>
            <RotateCcw size={17} aria-hidden="true" />
            다시 생성하기
          </button>
          <button className={styles.primaryButton} type="button">
            선택한 시안 편집하기 <Sparkles size={18} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button" onClick={onGoHome}>
            <Home size={17} aria-hidden="true" />
            홈으로
          </button>
          <button className={styles.secondaryButton} type="button" onClick={onBrowseSimilar}>
            <Share2 size={17} aria-hidden="true" />
            비슷한 스타일 더 보기
          </button>
        </div>
        <button className={styles.textButton} type="button">
          <Download size={16} aria-hidden="true" />
          선택한 시안 저장하기
        </button>
      </div>
    </>
  );
}
