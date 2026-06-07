"use client";

import React from "react";
import { Home, Info, RotateCcw, Sparkles } from "lucide-react";
import { getGenerationEngineOption } from "@/lib/generation-engine";
import {
  getGenerationResultNotice,
  getResultArtifactPayload
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
  onDelete?: () => void;
};

function cleanLabel(value: string | null | undefined) {
  return value?.trim() ?? "";
}

export function GenerationCompleteStep({
  state,
  onBrowseSimilar,
  onGoHome,
  onRegenerate,
  onOpenArchive,
  onDelete
}: GenerationCompleteStepProps) {
  const generatedJob = state.generationJob ?? null;
  const resultPayload = getResultArtifactPayload(generatedJob);
  const resultNotice = getGenerationResultNotice(generatedJob);
  const fallbackErrorMessage = !generatedJob ? state.errorMessage : null;
  const selectedEngineLabel =
    (typeof generatedJob?.metadata?.selected_engine_label === "string" ? generatedJob.metadata.selected_engine_label : "") ||
    getGenerationEngineOption(state.selectedImageGenerationEngine).modelName;
  const isFailed = generatedJob?.status === "failed" || Boolean(fallbackErrorMessage);
  const isDone = generatedJob?.status === "done" || generatedJob?.status === "completed";
  const canOpenArchive = isDone && resultNotice.level === "success";
  const isStoragePending = isDone && !canOpenArchive;
  const isInProgress = Boolean(generatedJob && !isDone && !isFailed);
  const title = isFailed
    ? "이미지 생성에 실패했어요"
    : canOpenArchive
      ? "광고 이미지 생성이 완료됐어요"
      : isStoragePending
        ? "이미지 저장 연결을 확인해야 해요"
      : isInProgress
        ? "광고 이미지 생성이 진행 중이에요"
        : "생성 요청 내역이 없어요";
  const description = isFailed
    ? fallbackErrorMessage || resultNotice.message
    : canOpenArchive
      ? "완성된 이미지는 보관함에서 확인할 수 있어요."
      : isStoragePending
        ? "이미지는 만들어졌지만 보관함에서 열 수 있는 주소를 아직 확인하지 못했어요."
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
      <StepHeader title="GENERATED RESULTS" canGoBack onBack={onGoHome} onDelete={onDelete} />

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
        <strong>
          {canOpenArchive
            ? "보관함에서 결과물을 확인해주세요"
            : isStoragePending
              ? "보관함 연결이 아직 끝나지 않았어요"
              : isFailed
                ? "요청을 다시 시도해주세요"
                : "생성 요청을 처리하고 있어요"}
        </strong>
        <p>
          {canOpenArchive
            ? "이미지 미리보기와 다운로드는 보관함에 저장된 결과 기준으로 보여드려요."
            : isStoragePending
              ? "저장 주소가 연결되지 않은 결과는 완료 이미지처럼 보여주지 않아요."
            : isFailed
              ? "실패한 요청은 임의 이미지로 대체하지 않아요."
              : "완료 전에는 깨진 이미지나 임시 카드를 보여주지 않아요."}
        </p>
      </section>

      {generatedJob ? (
        <p className={styles.savedNotice} data-result-notice-level={resultNotice.level}>
          <Info size={18} aria-hidden="true" />
          {resultNotice.message}
        </p>
      ) : fallbackErrorMessage ? (
        <p className={styles.savedNotice} data-result-notice-level="error">
          <Info size={18} aria-hidden="true" />
          {fallbackErrorMessage}
        </p>
      ) : null}

      <ValidationSummaryPanel payload={resultPayload} />

      <div className={styles.stepFooter}>
        <div className={`${styles.actionGrid} ${styles.generatedResultActions}`}>
          <button className={styles.primaryButton} type="button" disabled={!canOpenArchive} onClick={onOpenArchive}>
            {canOpenArchive ? "보관함에서 확인하기" : "보관함 연결 대기 중"} <Sparkles size={18} aria-hidden="true" />
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
