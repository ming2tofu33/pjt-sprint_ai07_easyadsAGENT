"use client";

import { Check, Clock3 } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { generationStageViewFromJob, generationStatusSteps } from "@/lib/generation-job-stage";
import { getGenerationEngineOption } from "@/lib/generation-engine";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationInProgressStepProps = {
  state: ChatFlowState;
  onBrowse: () => void;
};

export function GenerationInProgressStep({ state, onBrowse }: GenerationInProgressStepProps) {
  const brief = buildBrief(state);
  const engine = getGenerationEngineOption(state.selectedImageGenerationEngine);
  const generationStage = generationStageViewFromJob(state.generationJob);

  return (
    <>
      <StepHeader title="광고 생성 중" />

      <section className={styles.generationHero} aria-label="광고 생성 진행 상황">
        <MascotImage role="generatingWait" decorative className={styles.generationMascot} />
        <h1>생성 결과를 준비하고 있어요</h1>
        <p>{brief.item} 광고 이미지가 준비되면 보관함에서 확인할 수 있어요.</p>
      </section>

      <section className={styles.statusCard}>
        <h2>진행 상황</h2>
        <p className={styles.engineStatusNote}>선택한 모델: {engine.modelName}</p>
        <div className={styles.statusList}>
          {generationStatusSteps.map((item, index) => {
            const isDone = generationStage.isTerminal && !generationStage.isFailed ? true : index < generationStage.activeStepIndex;
            const isActive = !generationStage.isTerminal && index === generationStage.activeStepIndex;
            return (
              <div className={styles.statusItem} data-state={isDone ? "done" : isActive ? "active" : "waiting"} key={item}>
                <span className={styles.statusIcon}>
                  {isDone ? <Check size={15} aria-hidden="true" /> : <Clock3 size={15} aria-hidden="true" />}
                </span>
                <span>{item}</span>
              </div>
            );
          })}
        </div>
      </section>

      <div className={styles.generationProgress}>
        <div className={styles.progressMeta}>
          <strong>현재 상태</strong>
          <span>
            {generationStage.label}
            {generationStage.progressPercent !== null ? <strong>{generationStage.progressPercent}%</strong> : null}
          </span>
        </div>
        <span
          className={`${styles.progressTrack} ${generationStage.progressPercent === null ? styles.indeterminateProgressTrack : ""}`}
          aria-hidden="true"
        >
          <span
            className={styles.progressBar}
            style={generationStage.progressPercent === null ? undefined : { width: `${generationStage.progressPercent}%` }}
          />
        </span>
        <p>{generationStage.detail}</p>
      </div>

      <section>
        <h2 className={styles.sectionTitle}>실제 생성 결과 준비</h2>
        <div className={styles.skeletonGrid} aria-label="생성 중인 광고 시안 미리보기">
          {Array.from({ length: 1 }).map((_, index) => (
            <div className={styles.skeletonCreative} key={index}>
              <span />
              <small>이미지 불러오는 중...</small>
            </div>
          ))}
        </div>
      </section>

      <div className={`${styles.stepFooter} ${styles.generationFooter}`}>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button">
            이 화면에서 기다리기
          </button>
          <button className={styles.primaryButton} type="button" onClick={onBrowse}>
            기다리는 동안 둘러보기
          </button>
        </div>
      </div>
    </>
  );
}
