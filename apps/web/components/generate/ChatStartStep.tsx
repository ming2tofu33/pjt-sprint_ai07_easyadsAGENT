"use client";

import { Coffee, Gift, Image as ImageIcon, Megaphone, MessageCircle, Send, Utensils } from "lucide-react";
import { type ChangeEvent, useRef, useState } from "react";
import type { ReferenceImageFields } from "@/types/marketing";
import { DEFAULT_IMAGE_GENERATION_ENGINE, type ImageGenerationEngine } from "@/lib/generation-engine";
import { readGenerationDraftPrompt, readGenerationRequestContext } from "@/lib/generation-request-context";
import { ChoiceChip } from "./ChoiceChip";
import { GenerationEngineSelector } from "./GenerationEngineSelector";
import { MascotImage } from "./MascotImage";
import { SmartChatInput } from "./SmartChatInput";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

const examples = [
  "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
  "삼겹살집 회식 손님 많이 오게 포스터 만들어줘",
  "네일샵 여름 이벤트 인스타 스토리 만들어줘"
];

const quickStarts = [
  { label: "카페 신메뉴", icon: Coffee },
  { label: "음식점 할인", icon: Utensils },
  { label: "뷰티 예약", icon: Gift },
  { label: "리뷰 이벤트", icon: MessageCircle },
  { label: "오픈 홍보", icon: Megaphone }
];

const acceptedReferenceMimeTypes = new Set(["image/png", "image/jpeg", "image/webp"]);

type ChatStartStepProps = {
  onSubmit: (
    prompt: string,
    options?: ReferenceImageFields & { imageGenerationEngine?: ImageGenerationEngine }
  ) => void;
  onBack: () => void;
  onGoHome: () => void;
  onHistory?: () => void;
  errorMessage?: string | null;
  initialPrompt?: string;
};

export function ChatStartStep({ onSubmit, onBack, onGoHome, onHistory, errorMessage = null, initialPrompt = "" }: ChatStartStepProps) {
  const referenceFileInputRef = useRef<HTMLInputElement | null>(null);
  const [referenceTemplateTitle] = useState(() => readGenerationRequestContext()?.selectedReferenceTemplateTitle ?? "");
  const [value, setValue] = useState(() => {
    const initialPromptValue = initialPrompt.trim();
    if (initialPromptValue) {
      return initialPromptValue;
    }
    const requestContext = readGenerationRequestContext();
    if (requestContext?.source === "reference_gallery") {
      return "";
    }
    return readGenerationDraftPrompt();
  });
  const [imageGenerationEngine, setImageGenerationEngine] = useState<ImageGenerationEngine>(DEFAULT_IMAGE_GENERATION_ENGINE);
  const [referenceImageFile, setReferenceImageFile] = useState<File | null>(null);
  const [referenceImageError, setReferenceImageError] = useState("");
  const canSubmit = value.trim().length > 0;
  const promptPlaceholder = referenceTemplateTitle
    ? `${referenceTemplateTitle} 스타일을 참고해 어떤 광고를 만들지 적어주세요`
    : "AI와 대화로 이미지를 생성하세요";

  function submitPrompt() {
    const prompt = value.trim();
    if (prompt.length > 0) {
      onSubmit(prompt, {
        imageGenerationEngine,
        referenceImageFile
      });
    }
  }

  function handleReferenceImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      return;
    }
    if (!acceptedReferenceMimeTypes.has(file.type)) {
      setReferenceImageFile(null);
      setReferenceImageError("PNG, JPG, WebP 이미지만 참고 이미지로 사용할 수 있어요.");
      return;
    }
    setReferenceImageFile(file);
    setReferenceImageError("");
  }

  return (
    <>
      <StepHeader title="대화로 찰떡 이미지 만들기" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onHistory ? undefined : onGoHome} onHistory={onHistory} />
      <section className={styles.hero}>
        <MascotImage role="chatWave" decorative priority className={styles.chatHeroMascot} />
        <h2 className={styles.heroTitle}>원하는 광고를 편하게 적어보세요.</h2>
        <p className={styles.heroCopy}>
          AI가 부족한 정보를 물어보며
          <br />
          광고 이미지를 완성해드려요.
        </p>
      </section>

      <h2 className={styles.sectionTitle}>예시로 시작해보기</h2>
      <div className={styles.exampleList}>
        {examples.map((example) => (
          <button className={styles.examplePill} key={example} type="button" onClick={() => setValue(example)}>
            <Gift size={15} aria-hidden="true" />
            <span>{example}</span>
          </button>
        ))}
      </div>

      <h2 className={styles.sectionTitle}>빠른 시작</h2>
      <div className={`${styles.chipGrid} ${styles.quickStartGrid}`}>
        {quickStarts.map(({ label, icon: Icon }) => (
          <ChoiceChip key={label} onClick={() => setValue(`${label} 광고 만들어줘`)}>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </ChoiceChip>
        ))}
      </div>

      <h2 className={styles.sectionTitle}>이미지 생성 모델</h2>
      <GenerationEngineSelector value={imageGenerationEngine} onChange={setImageGenerationEngine} />

      <input
        ref={referenceFileInputRef}
        aria-label="레퍼런스 이미지 첨부"
        accept="image/png,image/jpeg,image/webp"
        className={styles.photoFileInput}
        type="file"
        onChange={handleReferenceImageChange}
      />
      <SmartChatInput
        className={styles.startInputCard}
        value={value}
        ariaLabel="광고 요청 입력"
        placeholder={promptPlaceholder}
        onChange={setValue}
        onSubmit={submitPrompt}
        leftControl={
          <button
            className={styles.inputIconButton}
            type="button"
            aria-label={referenceImageFile ? `첨부한 레퍼런스 이미지 ${referenceImageFile.name}` : "레퍼런스 이미지 선택"}
            onClick={() => referenceFileInputRef.current?.click()}
          >
            <ImageIcon size={19} aria-hidden="true" />
          </button>
        }
        rightControl={
          <button className={styles.sendButton} type="button" aria-label="요청 보내기" disabled={!canSubmit} onClick={submitPrompt}>
            <Send size={18} aria-hidden="true" />
          </button>
        }
      />
      {referenceImageFile ? <p className={styles.referenceAttachmentNote}>참고 이미지: {referenceImageFile.name}</p> : null}
      {referenceImageError ? <p className={styles.referenceAttachmentNote}>{referenceImageError}</p> : null}
      {errorMessage ? (
        <p className={styles.helperText} role="alert">{errorMessage}</p>
      ) : (
        <p className={styles.helperText}>대충 써도 괜찮아요. AI가 찰떡같이 알아들을게요.</p>
      )}
    </>
  );
}
