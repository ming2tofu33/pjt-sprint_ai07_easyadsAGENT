"use client";

import { Check, Clock3, Sparkles } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationInProgressStepProps = {
  state: ChatFlowState;
  progress: number;
  onBrowse: () => void;
};

const statusItems = [
  "광고 브리프 정리 완료",
  "문구와 이미지 방향 구성 완료",
  "광고 시안 생성 중",
  "결과 확인 준비 중"
];

export function GenerationInProgressStep({ state, progress, onBrowse }: GenerationInProgressStepProps) {
  const brief = buildBrief(state);
  const safeProgress = Math.max(12, Math.min(progress, 100));

  return (
    <>
      <StepHeader title="광고 생성 중" />

      <section className={styles.generationHero} aria-label="광고 생성 진행 상황">
        <span className={styles.generatingOrb}>
          <Sparkles size={24} aria-hidden="true" />
        </span>
        <h1>찰떡 광고를 만들고 있어요</h1>
        <p>{brief.item}에 어울리는 문구와 이미지를 조합하는 중이에요.</p>
      </section>

      <section className={styles.statusCard}>
        <h2>진행 상황</h2>
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
        <p>약 {Math.max(5, Math.ceil((100 - safeProgress) / 4))}초 남았어요</p>
      </div>

      <section>
        <h2 className={styles.sectionTitle}>생성 중인 광고 시안</h2>
        <div className={styles.skeletonGrid} aria-label="생성 중인 광고 시안 미리보기">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className={styles.skeletonCreative} key={index}>
              <span />
              <small>생성 중...</small>
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
