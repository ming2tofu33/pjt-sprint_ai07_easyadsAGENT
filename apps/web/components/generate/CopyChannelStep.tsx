"use client";

import clsx from "clsx";
import { Check, Instagram, PenLine } from "lucide-react";
import type { ChatFlowState, CopyCandidateOrigin } from "@/types/marketing";
import { channelOptions } from "@/lib/chat-flow";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

type CopyChannelStepProps = {
  state: ChatFlowState;
  onSelectCopy: (copyId: string) => void;
  onSelectChannel: (channelId: string) => void;
  onCustomDirection: (value: string) => void;
  onContinue: () => void;
  onBack: () => void;
  onDelete?: () => void;
};

export function CopyChannelStep({
  state,
  onSelectCopy,
  onSelectChannel,
  onCustomDirection,
  onContinue,
  onBack,
  onDelete
}: CopyChannelStepProps) {
  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <CopyChannelCard
        state={state}
        onSelectCopy={onSelectCopy}
        onSelectChannel={onSelectChannel}
        onCustomDirection={onCustomDirection}
        onContinue={onContinue}
      />
    </ChatTimelineStep>
  );
}

type CopyChannelCardProps = Omit<CopyChannelStepProps, "onBack" | "onDelete">;

function copyCandidateOriginLabel(origin: CopyCandidateOrigin): string {
  if (origin === "llm") {
    return "AI 생성";
  }
  if (origin === "fallback") {
    return "안전 추천";
  }
  if (origin === "rule_based") {
    return "자동 추천";
  }
  return "요청 기반";
}

function copyCandidateOriginNote(origin: CopyCandidateOrigin): string {
  if (origin === "llm") {
    return "AI가 이번 요청을 바탕으로 만든 문구 후보예요. 선택한 문구가 이미지에 반영됩니다.";
  }
  if (origin === "fallback") {
    return "AI 응답 대신 요청 정보를 바탕으로 안전한 추천 문구를 준비했어요. 선택한 문구가 이미지에 반영됩니다.";
  }
  if (origin === "rule_based") {
    return "요청 정보를 바탕으로 어울리는 추천 문구를 준비했어요. 선택한 문구가 이미지에 반영됩니다.";
  }
  return "이번 요청을 바탕으로 준비된 문구 후보예요. 선택한 문구가 이미지에 반영됩니다.";
}

export function CopyChannelCard({
  state,
  onSelectCopy,
  onSelectChannel,
  onCustomDirection,
  onContinue
}: CopyChannelCardProps) {
  const hasBackendSession = Boolean(state.jobId && state.threadId);
  const hasBackendCopyCandidates = state.copyCandidateSource === "backend" && state.copyCandidates.length > 0;
  const originLabel = copyCandidateOriginLabel(state.copyCandidateOrigin);
  const originNote = copyCandidateOriginNote(state.copyCandidateOrigin);
  const cannotContinue = state.isLoading || !hasBackendSession || !hasBackendCopyCandidates;

  return (
    <>
      <h2 className={styles.timelineSectionTitle}>문구와 채널을 골라주세요</h2>

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>분위기까지 좋습니다! 이제 어울리는 문구와 사용할 채널을 선택해볼까요?</p>
      </div>

      <div className={styles.copySectionHeader}>
        <h2 className={styles.sectionTitle}>추천 문구</h2>
        {hasBackendCopyCandidates ? <span>{originLabel}</span> : null}
      </div>
      <p className={styles.copySourceNote}>
        {hasBackendCopyCandidates
          ? originNote
          : "아직 이번 요청에 맞는 문구 후보를 받지 못했어요."}
      </p>
      {hasBackendCopyCandidates ? (
        <div className={styles.selectList}>
          {state.copyCandidates.map((copy, index) => {
            const selected = state.selectedCopyId === copy.id;
            const copyDetail = [copy.subcopy, copy.cta].filter(Boolean).join(" · ");
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
                  {copyDetail ? <small>{copyDetail}</small> : null}
                </span>
                {selected ? <Check size={19} aria-hidden="true" /> : <span />}
              </button>
            );
          })}
        </div>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="문구 후보 없음">
          <MascotImage role="copyEmpty" decorative className={styles.emptyMascot} />
          <strong>문구 후보가 아직 없어요</strong>
          <p>이번 응답에 문구 후보가 없어서 실제 이미지 생성을 진행하지 않습니다. 요청을 다시 보내주세요.</p>
        </section>
      )}

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
          <p className={styles.helperText}>생성 연결 정보를 먼저 받아야 실제 이미지 생성을 요청할 수 있어요.</p>
        ) : null}
        {!state.errorMessage && hasBackendSession && !hasBackendCopyCandidates ? (
          <p className={styles.helperText}>이번 요청에 맞는 문구 후보를 받은 뒤 브리프를 만들 수 있어요.</p>
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
