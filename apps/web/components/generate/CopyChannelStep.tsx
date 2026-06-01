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
  const hasBackendSession = Boolean(state.jobId && state.threadId);
  const hasBackendCopyCandidates = state.copyCandidateSource === "backend";
  const cannotContinue = state.isLoading || !hasBackendSession || !hasBackendCopyCandidates;
  const copySourceLabel = hasBackendCopyCandidates ? "백엔드 생성" : "샘플 문구";

  return (
    <>
      <StepHeader title="문구와 채널을 골라주세요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>분위기까지 좋습니다! 이제 어울리는 문구와 사용할 채널을 선택해볼까요?</p>
      </div>

      <div className={styles.copySectionHeader}>
        <h2 className={styles.sectionTitle}>{hasBackendCopyCandidates ? "AI 추천 문구" : "샘플 문구"}</h2>
        <span>{copySourceLabel}</span>
      </div>
      <p className={styles.copySourceNote}>
        {hasBackendCopyCandidates
          ? "백엔드가 이번 요청을 바탕으로 생성한 문구 후보예요."
          : "백엔드 문구 후보를 아직 받지 못해 샘플을 표시하고 있어요."}
      </p>
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
              <span className={styles.copyContent}>
                <span>{copy.headline}</span>
                <small>{copySourceLabel}</small>
              </span>
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
        {state.errorMessage ? <p className={styles.helperText}>{state.errorMessage}</p> : null}
        {!state.errorMessage && !hasBackendSession ? (
          <p className={styles.helperText}>백엔드 세션을 먼저 받아야 실제 이미지 생성을 요청할 수 있어요.</p>
        ) : null}
        {!state.errorMessage && hasBackendSession && !hasBackendCopyCandidates ? (
          <p className={styles.helperText}>샘플 문구로는 실제 이미지 생성을 진행하지 않아요. 다시 요청해 백엔드 문구를 받아주세요.</p>
        ) : null}
        <div className={styles.progressWrap}>
          <span>
            정보 입력 {state.progress.current}/{state.progress.total}
          </span>
          <span className={styles.progressTrack}>
            <span className={styles.progressBar} style={{ width: "75%" }} />
          </span>
        </div>

        <button className={styles.primaryButton} type="button" disabled={cannotContinue} onClick={onContinue}>
          {state.isLoading ? "이미지 생성 준비 중..." : "브리프 확인하기"}
        </button>
      </div>
    </>
  );
}
