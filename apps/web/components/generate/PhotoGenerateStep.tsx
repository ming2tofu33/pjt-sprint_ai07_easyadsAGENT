"use client";

import {
  ArrowRight,
  Camera,
  Check,
  ChevronRight,
  ImagePlus,
  Instagram,
  MessageCircle,
  Package,
  RefreshCw,
  Send,
  Sparkles,
  Store,
  Upload,
  Utensils
} from "lucide-react";
import { useMemo, useState } from "react";
import { channelOptions, toneOptions } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type PhotoGenerateStepProps = {
  onBack: () => void;
  onGoHome: () => void;
  onOpenChat: () => void;
  onGenerate: () => void;
};

const photoKinds = [
  { label: "음식 사진", icon: Utensils },
  { label: "제품 사진", icon: Package },
  { label: "매장/인테리어", icon: Store },
  { label: "로고", icon: ImagePlus }
];

const goals = ["신메뉴 출시", "시즌 한정 메뉴", "할인 이벤트", "인스타 감성 피드", "스토리 홍보", "리뷰 이벤트"];
const copyCandidates = [
  "봄을 닮은 한 잔, 딸기라떼 출시",
  "오늘만 더 달콤하게, 신메뉴 딸기라떼",
  "딸기 한가득, 지금 가장 상큼한 메뉴"
];

export function PhotoGenerateStep({ onBack, onGoHome, onOpenChat, onGenerate }: PhotoGenerateStepProps) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [goal, setGoal] = useState("신메뉴 출시");
  const [copy, setCopy] = useState(copyCandidates[0]);
  const [tone, setTone] = useState("감성적인");
  const [channel, setChannel] = useState("instagram-feed");
  const [direction, setDirection] = useState("");

  const selectedChannel = useMemo(
    () => channelOptions.find((item) => item.id === channel) ?? channelOptions[0],
    [channel]
  );

  function goBack() {
    if (step === 1) {
      onBack();
      return;
    }
    setStep((current) => Math.max(1, current - 1) as 1 | 2 | 3 | 4);
  }

  return (
    <>
      <StepHeader title={step === 1 ? "사진으로 찰떡 만들기" : "내 사진으로 만들기"} canGoBack backLabel="이전 화면" onBack={goBack} onHome={onGoHome} />

      {step === 1 ? (
        <>
          <section className={styles.photoDropzone}>
            <span>
              <Upload size={28} aria-hidden="true" />
            </span>
            <h2>사진을 끌어오거나 선택하세요</h2>
            <p>JPG, PNG · 최대 10MB</p>
          </section>

          <h2 className={styles.sectionTitle}>어떤 사진을 올릴 수 있나요?</h2>
          <div className={styles.photoKindGrid}>
            {photoKinds.map(({ label, icon: Icon }) => (
              <button key={label} type="button">
                <Icon size={20} aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          <h2 className={styles.sectionTitle}>최근 업로드</h2>
          <button className={styles.photoRecentCard} type="button">
            <div className={styles.photoThumb} aria-hidden="true" />
            <span>
              <strong>strawberry_latte.jpg</strong>
              <small>1.2MB · 2024.05.23</small>
            </span>
            <Check size={18} aria-hidden="true" />
          </button>

          <p className={styles.photoTip}>
            <Sparkles size={17} aria-hidden="true" />
            AI가 사진을 보고 광고 방향과 문구를 제안해드려요.
          </p>

          <div className={styles.stepFooter}>
            <button className={styles.primaryButton} type="button" onClick={() => setStep(2)}>
              다음 단계 <ArrowRight size={18} aria-hidden="true" />
            </button>
          </div>
        </>
      ) : null}

      {step === 2 ? (
        <>
          <section className={styles.photoAnalysisCard}>
            <div className={styles.photoPreview} aria-hidden="true" />
            <div>
              <h2>AI 분석 결과</h2>
              <p>사진에서 발견한 요소</p>
              <ul>
                <li>딸기라떼 음료</li>
                <li>밝은 자연광</li>
                <li>핑크·크림톤</li>
                <li>감성적인 카페 무드</li>
              </ul>
            </div>
          </section>

          <h2 className={styles.sectionTitle}>이 사진으로 어떤 광고를 만들까요?</h2>
          <div className={styles.photoGoalGrid}>
            {goals.map((item) => (
              <button data-active={goal === item ? "true" : undefined} key={item} type="button" onClick={() => setGoal(item)}>
                <Camera size={16} aria-hidden="true" />
                {item}
              </button>
            ))}
          </div>

          <label className={styles.photoPromptCard}>
            <input
              aria-label="직접 원하는 광고 방향 입력"
              placeholder="예: 봄 느낌으로 신메뉴 홍보 광고"
              value={direction}
              onChange={(event) => setDirection(event.target.value)}
            />
            <Send size={17} aria-hidden="true" />
          </label>

          <div className={styles.stepFooter}>
            <button className={styles.primaryButton} type="button" onClick={() => setStep(3)}>
              문구와 분위기 선택하기
            </button>
          </div>
        </>
      ) : null}

      {step === 3 ? (
        <>
          <h2 className={styles.sectionTitle}>추천 문구</h2>
          <div className={styles.selectList}>
            {copyCandidates.map((item) => (
              <button className={`${styles.copyCard} ${copy === item ? styles.copyCardSelected : ""}`} key={item} type="button" onClick={() => setCopy(item)}>
                <span className={styles.copyNumber}>{copyCandidates.indexOf(item) + 1}</span>
                <span>{item}</span>
                {copy === item ? <Check size={17} aria-hidden="true" /> : <ChevronRight size={17} aria-hidden="true" />}
              </button>
            ))}
          </div>

          <h2 className={styles.sectionTitle}>분위기는 어떤 느낌이 좋나요?</h2>
          <div className={styles.chipGrid}>
            {toneOptions.slice(0, 6).map((item) => (
              <button className={`${styles.chip} ${tone === item.label ? styles.chipSelected : ""}`} key={item.id} type="button" onClick={() => setTone(item.label)}>
                {item.label}
              </button>
            ))}
          </div>

          <h2 className={styles.sectionTitle}>어디에 사용할 건가요?</h2>
          <div className={styles.channelGrid}>
            {channelOptions.map((item) => (
              <button className={`${styles.channelCard} ${channel === item.id ? styles.channelCardSelected : ""}`} key={item.id} type="button" onClick={() => setChannel(item.id)}>
                <Instagram size={17} aria-hidden="true" />
                <span>{item.label}</span>
                <small>{item.ratio}</small>
              </button>
            ))}
          </div>

          <div className={styles.stepFooter}>
            <button className={styles.primaryButton} type="button" onClick={() => setStep(4)}>
              브리프 확인하기
            </button>
          </div>
        </>
      ) : null}

      {step === 4 ? (
        <>
          <section className={styles.photoBriefPreview}>
            <div className={styles.photoPreview} aria-hidden="true" />
            <button className={styles.secondaryButton} type="button" onClick={() => setStep(1)}>
              사진 다시 선택
            </button>
          </section>

          <section className={styles.briefCard}>
            <h2 className={styles.briefTitle}>AI가 브리프를 정리했어요</h2>
            <dl className={styles.photoBriefList}>
              <div><dt>광고 목적</dt><dd>{goal}</dd></div>
              <div><dt>상품/서비스</dt><dd>딸기라떼</dd></div>
              <div><dt>추천 문구</dt><dd>{copy}</dd></div>
              <div><dt>분위기</dt><dd>{tone}이고 따뜻한 카페 무드</dd></div>
              <div><dt>사용 채널</dt><dd>{selectedChannel.label} ({selectedChannel.ratio})</dd></div>
              <div><dt>핵심 색감</dt><dd><span className={styles.photoSwatches} aria-label="핑크, 코랄, 크림, 라임 색상" /></dd></div>
            </dl>
          </section>

          <p className={styles.photoTip}>
            <Sparkles size={17} aria-hidden="true" />
            이 내용으로 사진의 분위기를 살린 광고 이미지를 생성할게요.
          </p>

          <div className={styles.stepFooter}>
            <button className={styles.primaryButton} type="button" onClick={onGenerate}>
              찰떡 광고 생성하기 <Sparkles size={18} aria-hidden="true" />
            </button>
            <button className={styles.secondaryButton} type="button" onClick={onOpenChat}>
              대화로 직접 입력하기 <MessageCircle size={17} aria-hidden="true" />
            </button>
          </div>
        </>
      ) : null}

      <div className={styles.photoProgress} aria-label={`사진 플로우 ${step}/4 단계`}>
        {[1, 2, 3, 4].map((item) => (
          <span data-active={item <= step ? "true" : undefined} key={item} />
        ))}
      </div>
    </>
  );
}
