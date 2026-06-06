"use client";

import React from "react";
import { Home, Info, RotateCcw, Sparkles } from "lucide-react";
import { getGenerationEngineOption } from "@/lib/generation-engine";
import {
  getGenerationResultNotice,
  getResultArtifactPayload,
  hasOnlyLocalArtifactPath
} from "@/lib/generation-result-utils";
import type { ChatFlowState } from "@/types/marketing";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import { ValidationSummaryPanel } from "./ValidationSummaryPanel";
import styles from "./generate.module.css";

type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
  onGoHome: () => void;
  onRegenerate: () => void;
  onOpenArchive: () => void;
};

function cleanLabel(value: string | null | undefined) {
  return value?.trim() ?? "";
}

export function GenerationCompleteStep({
  state,
  onBrowseSimilar,
  onGoHome,
  onRegenerate,
  onOpenArchive
}: GenerationCompleteStepProps) {
  const generatedJob = state.generationJob ?? null;
  const resultPayload = getResultArtifactPayload(generatedJob);
  const resultNotice = getGenerationResultNotice(generatedJob);
  const hasLocalOnlyArtifact = hasOnlyLocalArtifactPath(resultPayload);
  const selectedEngineLabel =
    (typeof generatedJob?.metadata?.selected_engine_label === "string" ? generatedJob.metadata.selected_engine_label : "") ||
    getGenerationEngineOption(state.selectedImageGenerationEngine).modelName;
  const isFailed = generatedJob?.status === "failed";
  const isDone = generatedJob?.status === "done" || generatedJob?.status === "completed";
  const isInProgress = Boolean(generatedJob && !isDone && !isFailed);
  const title = isFailed
    ? "이미지 생성에 실패했어요"
    : isDone
      ? "광고 이미지 생성이 완료됐어요"
      : isInProgress
        ? "광고 이미지 생성이 진행 중이에요"
        : "생성 요청 내역이 없어요";
  const description = isFailed
    ? resultNotice.message
    : isDone
      ? "완성된 이미지는 보관함에서 확인할 수 있어요."
      : isInProgress
        ? "완료되면 보관함에 자동으로 정리돼요."
        : "대화로 광고를 만들면 생성 요청 상태가 여기에 표시돼요.";
  const chips = [
    selectedEngineLabel,
    generatedJob?.status ?? null,
    cleanLabel(state.inferredContext.businessType),
    cleanLabel(state.inferredContext.itemOrService),
    cleanLabel(state.inferredContext.promotionGoal)
  ].filter((chip): chip is string => Boolean(chip));

  return (
    <>
      <StepHeader title="GENERATED RESULTS" canGoBack onBack={onGoHome} />

      <header className={styles.resultsHeader}>
        <MascotImage role={isFailed ? "errorWorried" : "completeCheck"} decorative className={styles.resultsMascot} />
        <h1>{title}</h1>
        <p>{description}</p>
        {chips.length > 0 ? (
          <div className={styles.resultChips} aria-label="생성 요청 정보">
            {chips.map((chip) => (
              <span key={chip}>{chip}</span>
            ))}
          </div>
        ) : null}
      </header>

      <section className={styles.emptyResultPanel} aria-label="보관함 안내">
        <strong>{isDone ? "보관함에서 결과물을 확인해주세요" : isFailed ? "요청을 다시 시도해주세요" : "생성 요청을 처리하고 있어요"}</strong>
        <p>
          {isDone
            ? "이미지 미리보기와 다운로드는 보관함에 저장된 결과 기준으로 보여드려요."
            : isFailed
              ? "실패한 요청은 임의 이미지로 대체하지 않아요."
              : "완료 전에는 깨진 이미지나 임시 카드를 보여주지 않아요."}
        </p>
      </section>

      {hasLocalOnlyArtifact ? (
        <p className={styles.savedNotice}>
          <Info size={18} aria-hidden="true" />
          이미지는 생성됐지만 보관함에서 확인할 수 있는 주소가 아직 연결되지 않았어요.
        </p>
      ) : null}

      {generatedJob ? (
        <p className={styles.savedNotice} data-result-notice-level={resultNotice.level}>
          <Info size={18} aria-hidden="true" />
          {resultNotice.message}
        </p>
      ) : null}

      <ValidationSummaryPanel payload={resultPayload} />

      <div className={styles.stepFooter}>
        <div className={`${styles.actionGrid} ${styles.generatedResultActions}`}>
          <button className={styles.primaryButton} type="button" onClick={onOpenArchive}>
            보관함에서 확인하기 <Sparkles size={18} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button" onClick={onRegenerate}>
            <RotateCcw size={17} aria-hidden="true" />
            새 요청으로 만들기
          </button>
          <button className={styles.secondaryButton} type="button" onClick={onGoHome}>
            <Home size={17} aria-hidden="true" />
            홈으로
          </button>
        </div>
        <button className={styles.textButton} type="button" onClick={onBrowseSimilar}>
          참고할 스타일 더 보기
        </button>
      </div>
    </>
  );
}
