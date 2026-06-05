"use client";

import { Coffee, Gift, Image as ImageIcon, Megaphone, MessageCircle, PenLine, Send, Sparkles, Utensils } from "lucide-react";
import { useState } from "react";
import type { CopyGenerationMode, CustomCopyFields } from "@/types/marketing";
import { DEFAULT_IMAGE_GENERATION_ENGINE, type ImageGenerationEngine } from "@/lib/generation-engine";
import { readGenerationDraftPrompt, readGenerationRequestContext } from "@/lib/generation-request-context";
import { AutosizeTextarea } from "./AutosizeTextarea";
import { ChoiceChip } from "./ChoiceChip";
import { GenerationEngineSelector } from "./GenerationEngineSelector";
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

type ChatStartStepProps = {
  onSubmit: (
    prompt: string,
    options?: CustomCopyFields & { copyGenerationMode?: CopyGenerationMode; imageGenerationEngine?: ImageGenerationEngine }
  ) => void;
  onBack: () => void;
  onGoHome: () => void;
};

export function ChatStartStep({ onSubmit, onBack, onGoHome }: ChatStartStepProps) {
  const [referenceTemplateTitle] = useState(() => readGenerationRequestContext()?.selectedReferenceTemplateTitle ?? "");
  const [value, setValue] = useState(() => {
    const requestContext = readGenerationRequestContext();
    if (requestContext?.source === "reference_gallery") {
      return "";
    }
    return readGenerationDraftPrompt();
  });
  const [copyGenerationMode, setCopyGenerationMode] = useState<CopyGenerationMode>("suggest_candidates");
  const [imageGenerationEngine, setImageGenerationEngine] = useState<ImageGenerationEngine>(DEFAULT_IMAGE_GENERATION_ENGINE);
  const [customHeadline, setCustomHeadline] = useState("");
  const [customSubcopy, setCustomSubcopy] = useState("");
  const usesCustomCopy = copyGenerationMode === "custom_input";
  const customHeadlineText = customHeadline.trim();
  const customSubcopyText = customSubcopy.trim();
  const canSubmit = value.trim().length > 0 && (!usesCustomCopy || customHeadlineText.length > 0);
  const promptPlaceholder = referenceTemplateTitle
    ? `${referenceTemplateTitle} 스타일을 참고해 어떤 광고를 만들지 적어주세요`
    : "광고 방향을 입력해주세요";

  function submitPrompt() {
    const prompt = value.trim();
    if (prompt.length > 0 && (!usesCustomCopy || customHeadlineText.length > 0)) {
      onSubmit(prompt, {
        copyGenerationMode,
        imageGenerationEngine,
        userCustomHeadline: usesCustomCopy ? customHeadlineText : undefined,
        userCustomSubcopy: usesCustomCopy && customSubcopyText ? customSubcopyText : undefined
      });
    }
  }

  return (
    <>
      <StepHeader title="대화로 찰떡 만들기" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onGoHome} />
      <section className={styles.hero}>
        <span className={styles.heroIcon}>
          <MessageCircle size={25} strokeWidth={2.4} />
        </span>
        <h2 className={styles.heroTitle}>원하는 광고를 편하게 적어보세요.</h2>
        <p className={styles.heroCopy}>AI가 부족한 정보를 물어보며 광고 브리프를 완성해드려요.</p>
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
          <ImageIcon size={16} aria-hidden="true" />
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
              aria-label="직접 메인 문구 입력"
              placeholder="광고에 넣을 메인 문구"
              onChange={(event) => setCustomHeadline(event.target.value)}
              onSubmit={submitPrompt}
            />
          </label>
          <label className={styles.customCopyField}>
            <span>보조 문구</span>
            <AutosizeTextarea
              className={styles.customCopyTextarea}
              value={customSubcopy}
              aria-label="직접 보조 문구 입력"
              placeholder="이벤트 상세나 안내 문구"
              onChange={(event) => setCustomSubcopy(event.target.value)}
              onSubmit={submitPrompt}
            />
          </label>
        </div>
      ) : null}

      <h2 className={styles.sectionTitle}>이미지 생성 모델</h2>
      <GenerationEngineSelector value={imageGenerationEngine} onChange={setImageGenerationEngine} />

      <div className={`${styles.inputCard} ${styles.startInputCard}`}>
        <ImageIcon size={19} aria-hidden="true" />
        <AutosizeTextarea
          className={`${styles.input} ${styles.promptTextarea}`}
          value={value}
          aria-label="광고 요청 입력"
          placeholder={promptPlaceholder}
          onChange={(event) => setValue(event.target.value)}
          onSubmit={submitPrompt}
        />
        <button className={styles.sendButton} type="button" aria-label="요청 보내기" disabled={!canSubmit} onClick={submitPrompt}>
          <Send size={18} aria-hidden="true" />
        </button>
      </div>
      <p className={styles.helperText}>대충 써도 괜찮아요. AI가 찰떡같이 알아들을게요.</p>
    </>
  );
}
