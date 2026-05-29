"use client";

import { CheckCircle2, Download, Home, RotateCcw, Share2, Sparkles } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { resultCreatives } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
  onGoHome: () => void;
  onRegenerate: () => void;
  onSaveCreative?: (title: string) => void;
  onEditCreative?: () => void;
};

const editActions = ["문구 더 짧게", "상품 더 크게", "핑크톤 줄이기", "여백 줄이기", "스토리용 변환", "+ 더보기"];

export function GenerationCompleteStep({
  state,
  onBrowseSimilar,
  onGoHome,
  onRegenerate,
  onSaveCreative,
  onEditCreative
}: GenerationCompleteStepProps) {
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
        {resultCreatives.map((creative, index) => (
          <AdCreativeCard
            creative={{ ...creative, subtitle: index === 0 ? brief.copy : creative.subtitle }}
            index={index}
            key={creative.id}
            onSave={() => onSaveCreative?.(creative.title)}
          />
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
          <button className={styles.primaryButton} type="button" onClick={onEditCreative}>
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
        <button className={styles.textButton} type="button" onClick={() => onSaveCreative?.("선택한 시안")}>
          <Download size={16} aria-hidden="true" />
          선택한 시안 저장하기
        </button>
      </div>
    </>
  );
}
