"use client";

import { Coffee, Gift, Image as ImageIcon, Megaphone, MessageCircle, Send, Utensils } from "lucide-react";
import { useState } from "react";
import { readGenerationDraftPrompt } from "@/lib/generation-request-context";
import { AutosizeTextarea } from "./AutosizeTextarea";
import { ChoiceChip } from "./ChoiceChip";
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
  onSubmit: (prompt: string) => void;
  onBack: () => void;
  onGoHome: () => void;
};

export function ChatStartStep({ onSubmit, onBack, onGoHome }: ChatStartStepProps) {
  const [value, setValue] = useState(() => readGenerationDraftPrompt());
  const canSubmit = value.trim().length > 0;

  function submitPrompt() {
    const prompt = value.trim();
    if (prompt.length > 0) {
      onSubmit(prompt);
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
      <div className={styles.chipGrid}>
        {quickStarts.map(({ label, icon: Icon }) => (
          <ChoiceChip key={label} onClick={() => setValue(`${label} 광고 만들어줘`)}>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </ChoiceChip>
        ))}
      </div>

      <div className={styles.inputCard}>
        <ImageIcon size={19} aria-hidden="true" />
        <AutosizeTextarea
          className={`${styles.input} ${styles.promptTextarea}`}
          value={value}
          aria-label="광고 요청 입력"
          placeholder="예: 우리 가게 신메뉴 인스타 광고 만들어줘"
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
