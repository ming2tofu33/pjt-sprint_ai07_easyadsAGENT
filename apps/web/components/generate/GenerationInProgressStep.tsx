"use client";

import { Check, Clock3 } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { getGenerationEngineOption } from "@/lib/generation-engine";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationInProgressStepProps = {
  state: ChatFlowState;
  progress: number;
  onBrowse: () => void;
};

const statusItems = [
  "광고 브리프 정리 완료",
  "이미지 생성 요청 완료",
  "생성 결과 불러오는 중",
  "결과 화면 준비 중"
];

export function GenerationInProgressStep({ state, progress, onBrowse }: GenerationInProgressStepProps) {
  const brief = buildBrief(state);
  const engine = getGenerationEngineOption(state.selectedImageGenerationEngine);
  const safeProgress = Math.max(12, Math.min(progress, 100));

  return (
    <>
      <StepHeader title="광고 생성 중" />

      <section className={styles.generationHero} aria-label="광고 생성 진행 상황">
        <MascotImage role="generatingWait" decorative className={styles.generationMascot} />
        <h1>생성 결과를 준비하고 있어요</h1>
        <p>{brief.item} 광고 이미지가 준비되면 실제 결과 화면으로 이동해요.</p>
      </section>

      <section className={styles.statusCard}>
        <h2>진행 상황</h2>
        <p className={styles.engineStatusNote}>선택한 모델: {engine.modelName}</p>
        <div className={styles.statusList}>
          {statusItems.map((item, index) => {
            const activeIndex = safeProgress >= 100 ? 3 : safeProgress >= 68 ? 2 : safeProgress >= 36 ? 1 : 0;
            const isDone = index < activeIndex;
            const isActive = index === activeIndex;
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
          <strong>전체 진행률</strong>
          <span>{safeProgress}%</span>
        </div>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: `${safeProgress}%` }} />
        </span>
        <p>실제 이미지가 준비되는 동안만 표시돼요.</p>
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
