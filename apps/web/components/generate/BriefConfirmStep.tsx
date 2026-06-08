"use client";

import { Gift, Heart, Megaphone, Package, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { BriefRow } from "./BriefRow";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

type BriefConfirmStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onGenerate: () => void;
  onDelete?: () => void;
};

export function BriefConfirmStep({ state, onBack, onGenerate, onDelete }: BriefConfirmStepProps) {
  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <BriefConfirmCard state={state} onGenerate={onGenerate} />
    </ChatTimelineStep>
  );
}

type BriefConfirmCardProps = Omit<BriefConfirmStepProps, "onBack" | "onDelete">;

export function BriefConfirmCard({ state, onGenerate }: BriefConfirmCardProps) {
  const brief = buildBrief(state);

  return (
    <>
      <h2 className={styles.timelineSectionTitle}>AI가 브리프를 정리했어요</h2>

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>아래 내용으로 이해했어요. 맞다면 이 브리프로 이미지를 생성할게요.</p>
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
        <p className={styles.completeNote}>내용이 다르면 이전 단계로 돌아가 수정한 뒤 생성해주세요.</p>

        <div className={`${styles.progressWrap} ${styles.finalProgress}`}>
          <span>
            정보 입력 {state.progress.current}/{state.progress.total}
          </span>
          <span className={styles.progressTrack}>
            <span className={styles.progressBar} style={{ width: "100%" }} />
          </span>
        </div>

        <button className={styles.primaryButton} type="button" onClick={onGenerate}>
          이 내용으로 이미지 생성 <Sparkles size={18} aria-hidden="true" />
        </button>
      </div>
    </>
  );
}
