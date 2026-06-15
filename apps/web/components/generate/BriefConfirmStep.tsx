"use client";

import { Gift, Heart, Megaphone, Package, Send, Sparkles, Star } from "lucide-react";
import { useState } from "react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { BriefRow } from "./BriefRow";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { MascotImage } from "./MascotImage";
import { SmartChatInput } from "./SmartChatInput";
import styles from "./generate.module.css";

type BriefConfirmStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onGenerate: () => void;
  onRefineBrief: (message: string) => void | Promise<void>;
  onDelete?: () => void;
  readOnly?: boolean;
};

export function BriefConfirmStep({ state, onBack, onGenerate, onRefineBrief, onDelete, readOnly = false }: BriefConfirmStepProps) {
  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={readOnly ? undefined : onDelete} title={readOnly ? "보관된 작업방" : "대화로 찰떡 만들기"}>
      <BriefConfirmCard state={state} onGenerate={onGenerate} onRefineBrief={onRefineBrief} readOnly={readOnly} />
    </ChatTimelineStep>
  );
}

type BriefConfirmCardProps = Omit<BriefConfirmStepProps, "onBack" | "onDelete">;

export function BriefConfirmCard({ state, onGenerate, onRefineBrief, readOnly = false }: BriefConfirmCardProps) {
  const [refinementText, setRefinementText] = useState("");
  const brief = buildBrief(state);
  const usesDeferredCopySelection = state.copyGenerationMode === "suggest_candidates";

  async function submitRefinement() {
    if (state.isLoading) {
      return;
    }
    const message = refinementText.trim();
    if (!message) {
      return;
    }
    try {
      await onRefineBrief(message);
      setRefinementText("");
    } catch {
      // Keep the user's text so they can retry after the inline error appears.
    }
  }

  return (
    <>
      <h2 className={styles.timelineSectionTitle}>AI가 브리프를 정리했어요</h2>

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>
          {readOnly ? "보관된 작업방이에요. 대화와 브리프를 다시 확인할 수 있어요." : "아래 내용으로 이해했어요. 맞다면 이 브리프로 이미지를 생성할게요."}
        </p>
      </div>

      <section className={styles.briefCard} aria-label="광고 브리프 요약">
        <div className={styles.briefTitleGroup}>
          <MascotImage role="checkPaper" decorative className={styles.briefTitleMascot} />
          <h2 className={styles.briefTitle}>광고 브리프 요약</h2>
        </div>
        <BriefRow icon={Megaphone} label="광고 목적" value={brief.purpose} />
        <BriefRow icon={Gift} label="상품/서비스" value={brief.item} />
        {usesDeferredCopySelection ? (
          <BriefRow icon={Heart} label="문구 선택" value="다음 단계에서 선택" />
        ) : (
          <BriefRow icon={Heart} label="선택한 문구" value={brief.copy} />
        )}
        <BriefRow icon={Star} label="분위기" value={brief.tone} />
        <BriefRow icon={Package} label="사용 채널" value={brief.channel} />
        <div className={styles.imageGuide}>
          <strong>추천 이미지 방향</strong>
          <p>{brief.imageDirection}</p>
        </div>
      </section>

      {readOnly ? (
        <section className={styles.archivedThreadNotice} aria-label="보관된 작업방 안내">
          <strong>보관된 작업방이에요</strong>
          <p>작업방 3개 제한에서는 제외됐어요. 대화와 브리프는 확인할 수 있지만 이어서 수정하거나 이미지를 다시 만들 수는 없어요.</p>
        </section>
      ) : (
        <section className={styles.briefRefinementArea} aria-label="브리프 추가 요청">
          <h3 className={styles.briefRefinementTitle}>더 반영할 내용이 있나요?</h3>
          <SmartChatInput
            className={styles.briefRefinementInputCard}
            value={refinementText}
            ariaLabel="브리프 추가 요청 입력"
            placeholder="예: 네일아트 사진을 더 크게 보여줘"
            disabled={state.isLoading}
            onChange={setRefinementText}
            onSubmit={submitRefinement}
            rightControl={
              <button
                className={styles.sendButton}
                type="button"
                aria-label="브리프 추가 요청 보내기"
                disabled={state.isLoading || refinementText.trim().length === 0}
                onClick={submitRefinement}
              >
                <Send size={18} aria-hidden="true" />
              </button>
            }
          />
          {state.errorMessage ? <p className={styles.helperText}>{state.errorMessage}</p> : null}
        </section>
      )}

      {!readOnly ? (
        <div className={styles.stepFooter}>
          <p className={styles.completeNote}>추가로 원하는 점이 있으면 아래 입력창에 남기거나, 준비되면 이미지를 생성해주세요.</p>

          <div className={`${styles.progressWrap} ${styles.finalProgress}`}>
            <span>
              정보 입력 {state.progress.current}/{state.progress.total}
            </span>
            <span className={styles.progressTrack}>
              <span className={styles.progressBar} style={{ width: "100%" }} />
            </span>
          </div>

          <button className={styles.primaryButton} type="button" disabled={state.isLoading} onClick={onGenerate}>
            이 내용으로 이미지 생성 <Sparkles size={18} aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </>
  );
}
