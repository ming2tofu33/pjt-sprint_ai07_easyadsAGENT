"use client";

import clsx from "clsx";
import { Check, Instagram, PenLine } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { channelOptions } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type CopyChannelStepProps = {
  state: ChatFlowState;
  onSelectCopy: (copyId: string) => void;
  onSelectChannel: (channelId: string) => void;
  onCustomDirection: (value: string) => void;
  onContinue: () => void;
  onBack: () => void;
};

export function CopyChannelStep({
  state,
  onSelectCopy,
  onSelectChannel,
  onCustomDirection,
  onContinue,
  onBack
}: CopyChannelStepProps) {
  return (
    <>
      <StepHeader title="문구와 채널을 골라주세요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>분위기까지 좋습니다! 이제 어울리는 문구와 사용할 채널을 선택해볼까요?</p>
      </div>

      <h2 className={styles.sectionTitle}>추천 문구</h2>
      <div className={styles.selectList}>
        {state.copyCandidates.map((copy, index) => {
          const selected = state.selectedCopyId === copy.id;
          return (
            <button
              key={copy.id}
              type="button"
              className={clsx(styles.copyCard, selected && styles.copyCardSelected)}
              aria-pressed={selected}
              onClick={() => onSelectCopy(copy.id)}
            >
              <span className={styles.copyNumber}>{index + 1}</span>
              <span>{copy.headline}</span>
              {selected ? <Check size={19} aria-hidden="true" /> : <span />}
            </button>
          );
        })}
      </div>

      <h2 className={styles.sectionTitle}>어디에 사용할까요?</h2>
      <div className={styles.channelGrid}>
        {channelOptions.map((channel) => {
          const selected = state.selectedChannelId === channel.id;
          return (
            <button
              key={channel.id}
              type="button"
              className={clsx(styles.channelCard, selected && styles.channelCardSelected)}
              aria-pressed={selected}
              onClick={() => onSelectChannel(channel.id)}
            >
              <span>{channel.label}</span>
              <small>{channel.ratio}</small>
              <Instagram size={16} aria-hidden="true" />
            </button>
          );
        })}
      </div>

      <h2 className={styles.sectionTitle}>직접 입력하기</h2>
      <label className={styles.textareaCard}>
        <textarea
          className={styles.textarea}
          value={state.customDirection}
          aria-label="원하는 문구나 이미지 방향 직접 입력"
          placeholder="원하는 문구나 내용이 있다면 입력해보세요."
          onChange={(event) => onCustomDirection(event.target.value)}
        />
        <PenLine size={18} aria-hidden="true" />
      </label>

      <div className={styles.stepFooter}>
        <div className={styles.progressWrap}>
          <span>
            정보 입력 {state.progress.current}/{state.progress.total}
          </span>
          <span className={styles.progressTrack}>
            <span className={styles.progressBar} style={{ width: "75%" }} />
          </span>
        </div>

        <button className={styles.primaryButton} type="button" onClick={onContinue}>
          브리프 확인하기
        </button>
      </div>
    </>
  );
}
