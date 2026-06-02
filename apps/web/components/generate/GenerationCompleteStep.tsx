"use client";

import { CheckCircle2, Download, Home, ImageOff, Info, RotateCcw, Share2, Sparkles } from "lucide-react";
import type { ChatBrief, ChatFlowState } from "@/types/marketing";
import {
  buildGenerationResultCopyText,
  getGenerationResultNotice,
  getResultArtifactPayload,
  hasOnlyLocalArtifactPath,
  isDownloadEnabled,
  resolveDownloadUrl,
  resolvePreviewImageUrl
} from "@/lib/generation-result-utils";
import type { CreativeTone } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type GenerationCompleteStepProps = {
  state: ChatFlowState;
  onBrowseSimilar: () => void;
  onGoHome: () => void;
  onRegenerate: () => void;
  onSaveCreative?: (title: string) => void;
  onEditCreative?: () => void;
  onSaveSelected?: (creativeId: string) => void;
};

function cleanLabel(value: string | null | undefined) {
  return value?.trim() ?? "";
}

function channelName(channel: string) {
  return channel.replace(/\s*\(.+\)/, "").trim();
}

function targetChannelAction(channel: string) {
  const label = channelName(channel);
  if (label.includes("스토리")) {
    return "피드용 변환";
  }
  if (label.includes("포스터")) {
    return "피드용 변환";
  }
  return "스토리용 변환";
}

function resolveBriefImageUrl(path: string | null | undefined) {
  if (!path) {
    return null;
  }
  if (/^https?:\/\//.test(path) || path.startsWith("/api/") || path.startsWith("/generated/")) {
    return path;
  }
  return null;
}

function creativeToneFromBrief(brief: ChatBrief): CreativeTone {
  const tone = `${brief.tone} ${brief.imageDirection}`;
  if (tone.includes("상큼") || tone.includes("복숭아")) {
    return "peach";
  }
  if (tone.includes("깔끔") || tone.includes("민트") || tone.includes("신뢰")) {
    return "mint";
  }
  if (tone.includes("고급") || tone.includes("프리미엄")) {
    return "cream";
  }
  if (tone.includes("강렬") || tone.includes("할인")) {
    return "sunny";
  }
  return "strawberry";
}

function buildEditActions(brief: ChatBrief) {
  const item = cleanLabel(brief.item) || "상품";
  const tone = cleanLabel(brief.tone).replace(/\s*분위기$/, "").replace(/\s*무드$/, "");
  return [
    "문구 더 짧게",
    `${item} 더 크게`,
    tone ? `${tone} 톤 조정` : "분위기 조정",
    "문구 여백 조정",
    targetChannelAction(brief.channel),
    "+ 더보기"
  ];
}

export function GenerationCompleteStep({
  state,
  onBrowseSimilar,
  onGoHome,
  onRegenerate,
  onSaveCreative,
  onEditCreative,
  onSaveSelected
}: GenerationCompleteStepProps) {
  const brief = state.brief;
  const generatedJob = state.generationJob ?? null;
  const resultPayload = getResultArtifactPayload(generatedJob);
  const resultNotice = getGenerationResultNotice(generatedJob);
  const generatedImageUrl =
    resolvePreviewImageUrl(generatedJob) ??
    resolveBriefImageUrl(brief?.finalImagePath);
  const downloadUrl = resolveDownloadUrl(generatedJob);
  const canDownload = isDownloadEnabled(generatedJob);
  const debugFinalPath = resultPayload?.final_image_path ?? resultPayload?.download_path ?? generatedJob?.output_path ?? brief?.finalImagePath ?? null;
  const hasLocalOnlyArtifact = hasOnlyLocalArtifactPath(resultPayload);
  const isDevelopment = process.env.NODE_ENV !== "production";
  const hasResultContext = Boolean(brief || generatedJob);
  const isDoneWithoutPublicUrl = generatedJob?.status === "done" && !generatedImageUrl;
  const resultChips = brief
    ? [
        state.inferredContext.businessType,
        brief.item,
        brief.purpose,
        state.selectedTone,
        channelName(brief.channel)
      ].map(cleanLabel).filter(Boolean)
    : [];
  const editActions = brief && generatedImageUrl ? buildEditActions(brief) : [];
  const resultTitle =
    cleanLabel(brief?.copy) ||
    cleanLabel(brief?.item) ||
    generatedJob?.job_id ||
    "생성 결과";
  const resultSubtitle = brief
    ? [cleanLabel(brief.item), cleanLabel(brief.channel)].filter(Boolean).join(" · ")
    : generatedJob
      ? `Status: ${generatedJob.status}`
      : "";
  const generatedCreative = generatedImageUrl && (brief || generatedJob)
    ? {
        id: state.jobId ? `generated-${state.jobId}` : generatedJob?.job_id ? `generated-${generatedJob.job_id}` : "generated-current",
        title: resultTitle,
        subtitle: resultSubtitle,
        format: brief?.channel.match(/\(([^)]+)\)/)?.[1] ?? cleanLabel(brief?.channel) ?? "Generated",
        imageUrl: generatedImageUrl,
        tone: brief ? creativeToneFromBrief(brief) : "cream",
        badge: "실제 생성",
        status: "saved" as const,
        channel: brief ? channelName(brief.channel) : "Generated",
        fileName: "final_0.png",
        fileType: "PNG" as const,
        storage: "세션 보관함",
        savedAt: "방금 생성",
        tags: brief
          ? [state.inferredContext.businessType, brief.item, brief.purpose, channelName(brief.channel)].map(cleanLabel).filter(Boolean)
          : [generatedJob?.status ?? "unknown"].filter(Boolean)
      }
    : null;

  return (
    <>
      <StepHeader title="GENERATED RESULTS" canGoBack onBack={onGoHome} />

      <header className={styles.resultsHeader}>
        <h1>
          {generatedImageUrl
            ? "찰떡 광고 시안이 완성됐어요"
            : isDoneWithoutPublicUrl
              ? "광고 시안 생성은 완료됐어요"
              : hasResultContext
                ? "이미지 생성이 진행 중이거나 표시할 수 없어요"
                : "생성된 시안이 아직 없어요"}
        </h1>
        <p>
          {generatedImageUrl
            ? "실제 생성된 결과만 먼저 보여드려요."
            : isDoneWithoutPublicUrl
              ? "생성 결과는 준비됐지만, 현재 브라우저에서 표시 가능한 이미지 URL이 아직 연결되지 않았어요."
              : hasResultContext
                ? "브리프나 생성 작업은 준비됐지만 표시할 실제 이미지가 없어요. public preview URL 연결 상태를 확인해주세요."
                : "대화로 광고를 생성하면 실제 결과와 선택한 문구가 여기에 표시됩니다."}
        </p>
        {resultChips.length > 0 ? (
          <div className={styles.resultChips} aria-label="광고 결과 태그">
            {resultChips.map((chip) => (
              <span key={chip}>{chip}</span>
            ))}
          </div>
        ) : null}
      </header>

      {generatedCreative ? (
        <section className={`${styles.resultGrid} ${styles.generatedResultGrid}`} aria-label="생성된 광고 시안">
          <AdCreativeCard
            creative={generatedCreative}
            index={0}
            onSave={() => onSaveCreative?.(generatedCreative.title)}
          />
        </section>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="생성 결과 없음">
          <ImageOff size={24} aria-hidden="true" />
          <strong>{hasResultContext ? "실제 이미지 파일을 받지 못했어요" : "표시할 생성 결과가 없어요"}</strong>
          <p>
            {hasResultContext
              ? "임의 카드로 대신 보여주지 않고, 실제 이미지가 준비된 경우에만 결과 카드를 표시합니다."
              : "먼저 대화로 광고를 만들면 이 화면에 실제 이미지와 브리프가 함께 표시됩니다."}
          </p>
        </section>
      )}

      <p className={styles.savedNotice}>
        {generatedImageUrl ? <CheckCircle2 size={18} aria-hidden="true" /> : <Info size={18} aria-hidden="true" />}
        {generatedImageUrl
          ? "이 결과는 이번 브라우저 세션의 보관함에 자동 저장됐어요."
          : hasResultContext
            ? "브라우저에서 표시 가능한 이미지 URL이 없어 이번 결과는 세션 보관함 카드로 저장하지 않았어요."
            : "아직 생성된 결과가 없어 보관함에 저장된 항목도 없어요."}
      </p>

      {generatedJob ? (
        <p className={styles.savedNotice} data-result-notice-level={resultNotice.level}>
          <Info size={18} aria-hidden="true" />
          {resultNotice.message}
        </p>
      ) : null}

      {!generatedImageUrl && hasLocalOnlyArtifact ? (
        <p className={styles.savedNotice}>
          Generation is complete, but a browser-displayable image URL is not connected yet. Download becomes available when an image URL is connected.
        </p>
      ) : null}

      {isDevelopment && debugFinalPath ? (
        <details className={styles.savedNotice}>
          <summary>Debug artifact details</summary>
          <span>{debugFinalPath}</span>
        </details>
      ) : null}

      {editActions.length > 0 ? (
        <div className={styles.editActionGrid} aria-label="빠른 수정 요청">
          {editActions.map((action) => (
            <button disabled={!generatedImageUrl} key={action} type="button">
              {action}
            </button>
          ))}
        </div>
      ) : null}

      <div className={styles.stepFooter}>
        <div className={`${styles.actionGrid} ${styles.generatedResultActions}`}>
          <button className={styles.secondaryButton} type="button" onClick={onRegenerate}>
            <RotateCcw size={17} aria-hidden="true" />
            새 요청으로 만들기
          </button>
        </div>
        <div className={styles.actionGrid}>
          <button className={styles.secondaryButton} type="button" onClick={onGoHome}>
            <Home size={17} aria-hidden="true" />
            홈으로
          </button>
          <button className={styles.secondaryButton} type="button" onClick={onBrowseSimilar}>
            <Share2 size={17} aria-hidden="true" />
            레퍼런스 갤러리 보기
          </button>
        </div>
        {generatedCreative ? (
          <>
            <div className={`${styles.actionGrid} ${styles.generatedResultActions}`}>
              <button className={styles.primaryButton} type="button" onClick={onEditCreative}>
                시안 편집하기 <Sparkles size={18} aria-hidden="true" />
              </button>
            </div>
            <button className={styles.textButton} type="button" onClick={() => onSaveSelected?.(generatedCreative.id)}>
              <Download size={16} aria-hidden="true" />
              세션 보관함에서 보기
            </button>
          </>
        ) : null}
        {generatedJob ? (
          <button
            className={styles.textButton}
            disabled={!canDownload}
            type="button"
            title={canDownload ? undefined : "이미지는 생성되었지만 public download URL은 아직 연결되지 않았습니다."}
            onClick={() => downloadUrl && window.open(downloadUrl, "_blank", "noopener,noreferrer")}
          >
            <Download size={16} aria-hidden="true" />
            {canDownload ? "다운로드" : "다운로드 준비 전"}
          </button>
        ) : null}
        {generatedJob ? (
          <button className={styles.textButton} type="button" onClick={() => navigator.clipboard?.writeText(buildGenerationResultCopyText(generatedJob))}>
            결과 정보 복사
          </button>
        ) : null}
      </div>
    </>
  );
}
