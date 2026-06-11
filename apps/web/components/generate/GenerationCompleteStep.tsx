"use client";

import React from "react";
import { Archive, CheckCircle2, Clock3, Home, Info, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
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
  const qualityDecision = typeof resultPayload?.qualityDecision === "string" ? resultPayload.qualityDecision : null;
  const ocrDecision = typeof resultPayload?.ocr_gate?.decision === "string" ? resultPayload.ocr_gate.decision : null;
  const complianceStatus = typeof resultPayload?.compliance?.status === "string" ? resultPayload.compliance.status : null;
  const isReviewBlocked = Boolean(
    isDone &&
      (resultNotice.level === "error" || resultNotice.level === "warning") &&
      (resultPayload?.qualityRejected ||
        resultPayload?.requiresManualReview ||
        ["reject", "manual_review", "unavailable", "retry_image", "retry_layout"].includes(qualityDecision ?? "") ||
        ["reject", "manual_review", "unavailable", "retry_image", "retry_layout"].includes(ocrDecision ?? "") ||
        ["blocked", "needs_review"].includes(complianceStatus ?? ""))
  );
  const isStoragePending = isDone && !canOpenArchive && !isReviewBlocked;
  const hasRequestContext = Boolean(
    generatedJob ||
      state.userInput.trim() ||
      state.brief ||
      cleanLabel(state.inferredContext.businessType) ||
      cleanLabel(state.inferredContext.itemOrService) ||
      cleanLabel(state.inferredContext.promotionGoal)
  );
  const isInProgress = Boolean((generatedJob && !isDone && !isFailed) || (!generatedJob && hasRequestContext && !isFailed));
  const isEmpty = !generatedJob && !fallbackErrorMessage && !hasRequestContext;
  const canNavigateToArchive = canOpenArchive || isStoragePending || isInProgress;
  const title = isFailed
    ? "이미지 생성에 실패했어요"
    : canOpenArchive
      ? "광고 이미지 생성이 완료됐어요"
      : isReviewBlocked && isDone
        ? "생성 결과 확인이 필요해요"
        : isStoragePending
          ? "이미지 저장 연결을 확인해야 해요"
          : isInProgress
            ? "이미지를 만들고 있어요"
            : "생성 요청 내역이 없어요";
  const description = isFailed
    ? fallbackErrorMessage || resultNotice.message
    : canOpenArchive
      ? "완성된 이미지는 보관함에서 확인할 수 있어요."
      : isReviewBlocked && isDone
        ? resultNotice.message
        : isStoragePending
          ? "이미지는 만들어졌지만 보관함에서 열 수 있는 주소를 아직 확인하지 못했어요."
          : isInProgress
            ? "완성되면 보관함에 자동으로 저장돼요. 잠시만 기다려주세요."
            : "대화로 광고를 만들면 생성 요청 상태가 여기에 표시돼요.";
  const headerTitle = isInProgress ? "생성 진행 상황" : "생성 결과";
  const chips = [
    selectedEngineLabel,
    generatedJob?.status ?? null,
    cleanLabel(state.inferredContext.businessType),
    cleanLabel(state.inferredContext.itemOrService),
    cleanLabel(state.inferredContext.promotionGoal)
  ].filter((chip): chip is string => Boolean(chip));
  const pendingSteps = [
    { label: "요청 접수 완료", state: generatedJob ? "done" : "active", icon: CheckCircle2 },
    { label: "광고 방향 정리", state: generatedJob ? "done" : "pending", icon: CheckCircle2 },
    { label: "이미지 생성", state: generatedJob ? "active" : "pending", icon: LoaderCircle },
    { label: "보관함 연결 확인", state: "pending", icon: Archive }
  ] as const;

  return (
    <>
      <StepHeader title={headerTitle} canGoBack onBack={onGoHome} onDelete={onDelete} />

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

      {isInProgress ? (
        <section className={styles.resultStatusPanel} aria-label="이미지 생성 진행 상황" data-result-state="pending">
          <div className={styles.pendingPreviewFrame}>
            <LoaderCircle size={26} aria-hidden="true" />
            <strong>미리보기는 완성 후 표시돼요</strong>
            <p>이미지가 준비되면 이 영역이 결과 카드로 바뀝니다.</p>
          </div>
          <ol className={styles.resultStatusList} aria-label="진행 단계">
            {pendingSteps.map((step) => {
              const Icon = step.icon;
              return (
                <li key={step.label} data-state={step.state}>
                  <span>
                    <Icon size={17} aria-hidden="true" />
                  </span>
                  {step.label}
                </li>
              );
            })}
          </ol>
        </section>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="보관함 안내" data-result-state={isEmpty ? "empty" : "resolved"}>
          <strong>
            {canOpenArchive
              ? "보관함에서 결과물을 확인해주세요"
              : isReviewBlocked && isDone
                ? "검수 결과를 확인해주세요"
              : isStoragePending
                ? "보관함 연결이 아직 끝나지 않았어요"
                : isFailed
                  ? "요청을 다시 시도해주세요"
                  : "아직 표시할 생성 요청이 없어요"}
          </strong>
          <p>
            {canOpenArchive
              ? "이미지 미리보기와 다운로드는 보관함에 저장된 결과 기준으로 보여드려요."
              : isReviewBlocked && isDone
                ? "사용하거나 보관함으로 이동하기 전에 검수 내용을 먼저 확인해주세요."
              : isStoragePending
                ? "저장 주소가 연결되지 않아 보관함에서 열 수 있는 결과만 기다리고 있어요."
              : isFailed
                ? "실패한 요청은 임의 이미지로 대체하지 않아요."
                : "대화로 광고를 만들면 생성 상태가 이곳에 표시됩니다."}
          </p>
        </section>
      )}

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
          <button className={styles.primaryButton} type="button" disabled={!canNavigateToArchive || isReviewBlocked} onClick={onOpenArchive}>
            {canOpenArchive || isStoragePending ? "보관함에서 확인하기" : isInProgress ? "보관함에서 기다리기" : "보관함 연결 대기 중"}{" "}
            {canOpenArchive ? <Sparkles size={18} aria-hidden="true" /> : <Clock3 size={18} aria-hidden="true" />}
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
