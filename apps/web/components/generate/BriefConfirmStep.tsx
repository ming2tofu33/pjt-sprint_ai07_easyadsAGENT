"use client";

import { Gift, Heart, Megaphone, Package, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { BriefRow } from "./BriefRow";
import { MascotImage } from "./MascotImage";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type BriefConfirmStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onGenerate: () => void;
};

export function BriefConfirmStep({ state, onBack, onGenerate }: BriefConfirmStepProps) {
  const brief = buildBrief(state);
  const hasGeneratedImage = Boolean(brief.finalImagePath);

  return (
    <>
      <StepHeader title="AI가 브리프를 정리했어요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>
          {hasGeneratedImage
            ? "실제 광고 이미지 생성이 완료됐어요. 이제 결과 화면에서 확인할 수 있어요."
            : "브리프는 정리됐지만 아직 표시할 실제 이미지를 받지 못했어요. 결과 화면에서 상태를 확인할 수 있어요."}
        </p>
      </div>

      <section className={styles.briefCard} aria-label="광고 브리프 요약">
        <div className={styles.briefTitleGroup}>
          <MascotImage role="checkPaper" decorative className={styles.briefTitleMascot} />
          <h2 className={styles.briefTitle}>광고 브리프 요약</h2>
        </div>
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

      <div className={styles.stepFooter}>
        <p className={styles.completeNote}>
          {hasGeneratedImage ? "생성된 이미지를 결과 화면에서 바로 확인해보세요." : "임의 카드로 대체하지 않고 실제 이미지가 준비된 경우에만 결과를 표시합니다."}
        </p>

        <div className={`${styles.progressWrap} ${styles.finalProgress}`}>
          <span>
            정보 입력 {state.progress.current}/{state.progress.total}
          </span>
          <span className={styles.progressTrack}>
            <span className={styles.progressBar} style={{ width: "100%" }} />
          </span>
        </div>

        <button className={styles.primaryButton} type="button" onClick={onGenerate}>
          {hasGeneratedImage ? "생성 결과 확인하기" : "결과 상태 확인하기"} <Sparkles size={18} aria-hidden="true" />
        </button>
      </div>
    </>
  );
}
