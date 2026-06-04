"use client";

import { FileImage, ImagePlus, MessageCircle, PenLine, Send, Sparkles, UploadCloud } from "lucide-react";
import { type ChangeEvent, type DragEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type { CopyGenerationMode, CustomCopyFields } from "@/types/marketing";
import { AutosizeTextarea } from "./AutosizeTextarea";
import { ChoiceChip } from "./ChoiceChip";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type PhotoGenerateInput = {
  file: File;
  prompt: string;
  copyGenerationMode?: CopyGenerationMode;
} & CustomCopyFields;

type PhotoGenerateStepProps = {
  onBack: () => void;
  onGoHome: () => void;
  onOpenChat: () => void;
  onGenerate: (input: PhotoGenerateInput) => Promise<void> | void;
};

const acceptedMimeTypes = new Set(["image/png", "image/jpeg", "image/webp"]);

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size}B`;
  }
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)}KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)}MB`;
}

export function PhotoGenerateStep({ onBack, onGoHome, onOpenChat, onGenerate }: PhotoGenerateStepProps) {
  const formRef = useRef<HTMLFormElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [copyGenerationMode, setCopyGenerationMode] = useState<CopyGenerationMode>("suggest_candidates");
  const [customHeadline, setCustomHeadline] = useState("");
  const [customSubcopy, setCustomSubcopy] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!selectedFile || typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
      setPreviewUrl(null);
      return undefined;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedFile]);

  const promptText = prompt.trim();
  const customHeadlineText = customHeadline.trim();
  const customSubcopyText = customSubcopy.trim();
  const usesCustomCopy = copyGenerationMode === "custom_input";
  const canSubmit = useMemo(
    () => Boolean(selectedFile && promptText) && (!usesCustomCopy || customHeadlineText.length > 0) && !isSubmitting,
    [customHeadlineText.length, isSubmitting, promptText, selectedFile, usesCustomCopy]
  );

  function acceptFile(file: File | null) {
    if (!file) {
      return;
    }
    if (!acceptedMimeTypes.has(file.type)) {
      setSelectedFile(null);
      setErrorMessage("PNG, JPG, WebP 형식의 사진만 사용할 수 있어요.");
      return;
    }
    setSelectedFile(file);
    setErrorMessage(null);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    acceptFile(event.target.files?.[0] ?? null);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    acceptFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || !promptText || (usesCustomCopy && !customHeadlineText)) {
      setErrorMessage(usesCustomCopy && !customHeadlineText ? "메인 문구를 입력해주세요." : "사진과 요청 내용을 모두 입력해주세요.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await onGenerate({
        file: selectedFile,
        prompt: promptText,
        copyGenerationMode,
        userCustomHeadline: usesCustomCopy ? customHeadlineText : undefined,
        userCustomSubcopy: usesCustomCopy && customSubcopyText ? customSubcopyText : undefined
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "사진 기반 생성 요청에 실패했습니다.");
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <StepHeader title="내 사진으로 만들기" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onGoHome} />

      <section className={styles.hero}>
        <span className={styles.heroIcon}>
          <ImagePlus size={25} strokeWidth={2.4} aria-hidden="true" />
        </span>
        <h2 className={styles.heroTitle}>사진과 광고 방향을 함께 보내주세요.</h2>
        <p className={styles.heroCopy}>AI가 사진을 참고해 필요한 정보를 확인하고 어울리는 문구를 제안해드려요.</p>
      </section>

      <form ref={formRef} className={styles.photoStartForm} onSubmit={handleSubmit}>
        <div
          className={styles.photoDropzone}
          data-has-file={selectedFile ? "true" : undefined}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            aria-label="광고 사진 선택"
            accept="image/png,image/jpeg,image/webp"
            className={styles.photoFileInput}
            type="file"
            onChange={handleFileChange}
          />
          {previewUrl ? (
            <span className={styles.photoPreviewFrame} style={{ backgroundImage: `url(${previewUrl})` }} aria-hidden="true" />
          ) : (
            <span>
              <UploadCloud size={24} aria-hidden="true" />
            </span>
          )}
          <h2>{selectedFile ? "사진이 선택됐어요" : "광고에 쓸 사진을 올려주세요"}</h2>
          <p>
            {selectedFile ? (
              <>
                <FileImage size={13} aria-hidden="true" /> {selectedFile.name} · {formatFileSize(selectedFile.size)}
              </>
            ) : (
              "PNG, JPG, WebP 파일을 사용할 수 있어요."
            )}
          </p>
          <button className={styles.photoUploadButton} type="button" onClick={() => fileInputRef.current?.click()}>
            <UploadCloud size={16} aria-hidden="true" />
            {selectedFile ? "다른 사진 선택" : "사진 선택하기"}
          </button>
        </div>

        <h2 className={styles.sectionTitle}>문구 포함 여부</h2>
        <div className={`${styles.chipGrid} ${styles.copyModeGrid}`}>
          <ChoiceChip selected={copyGenerationMode === "suggest_candidates"} onClick={() => setCopyGenerationMode("suggest_candidates")}>
            <MessageCircle size={16} aria-hidden="true" />
            <span>문구도 추천</span>
          </ChoiceChip>
          <ChoiceChip selected={copyGenerationMode === "auto_pilot"} onClick={() => setCopyGenerationMode("auto_pilot")}>
            <Sparkles size={16} aria-hidden="true" />
            <span>AI 자동 완성</span>
          </ChoiceChip>
          <ChoiceChip selected={copyGenerationMode === "no_copy"} onClick={() => setCopyGenerationMode("no_copy")}>
            <ImagePlus size={16} aria-hidden="true" />
            <span>이미지만 생성</span>
          </ChoiceChip>
          <ChoiceChip selected={copyGenerationMode === "custom_input"} onClick={() => setCopyGenerationMode("custom_input")}>
            <PenLine size={16} aria-hidden="true" />
            <span>직접 문구</span>
          </ChoiceChip>
        </div>

        {usesCustomCopy ? (
          <div className={styles.customCopyFields}>
            <label className={styles.customCopyField}>
              <span>메인 문구</span>
              <AutosizeTextarea
                className={styles.customCopyTextarea}
                value={customHeadline}
                aria-label="사진 직접 메인 문구 입력"
                placeholder="광고에 넣을 메인 문구"
                onChange={(event) => {
                  setCustomHeadline(event.target.value);
                  if (errorMessage) {
                    setErrorMessage(null);
                  }
                }}
                onSubmit={() => formRef.current?.requestSubmit()}
              />
            </label>
            <label className={styles.customCopyField}>
              <span>보조 문구</span>
              <AutosizeTextarea
                className={styles.customCopyTextarea}
                value={customSubcopy}
                aria-label="사진 직접 보조 문구 입력"
                placeholder="이벤트 상세나 안내 문구"
                onChange={(event) => {
                  setCustomSubcopy(event.target.value);
                  if (errorMessage) {
                    setErrorMessage(null);
                  }
                }}
                onSubmit={() => formRef.current?.requestSubmit()}
              />
            </label>
          </div>
        ) : null}

        <label className={styles.photoPromptCard}>
          <AutosizeTextarea
            className={styles.photoPromptTextarea}
            aria-label="사진 광고 요청 입력"
            placeholder="광고 방향을 입력해주세요"
            value={prompt}
            onChange={(event) => {
              setPrompt(event.target.value);
              if (errorMessage) {
                setErrorMessage(null);
              }
            }}
            onSubmit={() => formRef.current?.requestSubmit()}
          />
          <Send size={17} aria-hidden="true" />
        </label>

        {errorMessage ? (
          <p className={styles.photoTip} role="alert">
            <Sparkles size={17} aria-hidden="true" />
            {errorMessage}
          </p>
        ) : (
          <p className={styles.photoTip}>
            <Sparkles size={17} aria-hidden="true" />
            선택한 사진과 입력한 방향을 바탕으로 다음 단계가 이어집니다.
          </p>
        )}

        <div className={styles.stepFooter}>
          <div className={styles.progressWrap} aria-label="사진 생성 준비">
            <span>사진 입력</span>
            <span className={styles.progressTrack}>
              <span className={styles.progressBar} style={{ width: selectedFile ? "50%" : "18%" }} />
            </span>
          </div>
          <button className={styles.primaryButton} disabled={!canSubmit} type="submit">
            {isSubmitting ? "사진을 보내는 중..." : "사진 기반 생성 시작"} <Sparkles size={18} aria-hidden="true" />
          </button>
          <button className={styles.secondaryButton} disabled={isSubmitting} type="button" onClick={onOpenChat}>
            대화로 시작하기 <MessageCircle size={17} aria-hidden="true" />
          </button>
        </div>
      </form>
    </>
  );
}
