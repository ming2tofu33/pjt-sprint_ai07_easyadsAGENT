"use client";

import { Gift, Heart, Megaphone, Package, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { BriefRow } from "./BriefRow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type BriefConfirmStepProps = {
  state: ChatFlowState;
  onBack: () => void;
};

export function BriefConfirmStep({ state, onBack }: BriefConfirmStepProps) {
  const brief = buildBrief(state);

  return (
    <>
      <StepHeader title="AI가 브리프를 정리했어요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>모든 정보가 준비됐어요. 이 내용으로 광고를 만들 준비가 완료됐어요.</p>
      </div>

      <section className={styles.briefCard} aria-label="광고 브리프 요약">
        <h2 className={styles.briefTitle}>광고 브리프 요약</h2>
        <BriefRow icon={Megaphone} label="광고 목적" value={brief.purpose} />
        <BriefRow icon={Gift} label="상품/서비스" value={brief.item} />
        <BriefRow icon={Heart} label="선택한 문구" value={brief.copy} />
        <BriefRow icon={Star} label="분위기" value={brief.tone} />
        <BriefRow icon={Package} label="사용 채널" value={brief.channel} />
        <div className={styles.imageGuide}>
          <strong>추천 이미지 방향</strong>
          <p>{brief.imageDirection}</p>
        </div>
      </section>

      <p className={styles.completeNote}>이 내용으로 광고 이미지를 생성할게요. 마음에 들지 않으면 언제든 수정할 수 있어요.</p>

      <button className={styles.primaryButton} type="button">
        찰떡 광고 생성하기 <Sparkles size={18} aria-hidden="true" />
      </button>

      <div className={`${styles.progressWrap} ${styles.finalProgress}`}>
        <span>
          정보 입력 {state.progress.current}/{state.progress.total}
        </span>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: "100%" }} />
        </span>
      </div>
    </>
  );
}
