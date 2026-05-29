"use client";

import {
  Bookmark,
  Briefcase,
  ChevronRight,
  Heart,
  MoreHorizontal,
  Palette,
  PenLine,
  Search,
  Share2,
  Sparkles,
  Store,
  Type,
  Utensils
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { brandFacts, getReferenceCreativeById, getSimilarReferenceCreatives, referenceCreatives } from "@/lib/mock-dashboard-data";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildReferenceStyleHref, type ReferenceStyleStep } from "@/lib/reference-navigation";
import { AdCreativeCard } from "./AdCreativeCard";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type ReferenceStyleFlowStepProps = {
  creativeId: string;
  step: ReferenceStyleStep;
};

const businessTypes = [
  { label: "카페", icon: Store },
  { label: "음식점", icon: Utensils },
  { label: "뷰티샵", icon: Sparkles },
  { label: "꽃집", icon: Heart },
  { label: "학원", icon: Briefcase },
  { label: "기타", icon: MoreHorizontal }
];

const similarCategories = ["전체", "카페", "음료", "디저트", "신메뉴", "감성"];

export function ReferenceStyleFlowStep({ creativeId, step }: ReferenceStyleFlowStepProps) {
  const router = useRouter();
  const creative = getReferenceCreativeById(creativeId) ?? referenceCreatives[0];
  const similarCreatives = useMemo(() => getSimilarReferenceCreatives(creative.id), [creative.id]);
  const [businessType, setBusinessType] = useState("카페");
  const [businessName, setBusinessName] = useState(brandFacts.name);

  const styleProfile = creative.styleProfile ?? referenceCreatives[0].styleProfile!;
  const tags = creative.tags ?? [creative.format, creative.badge ?? "추천 스타일"];

  function goBack() {
    if (step === "detail") {
      router.push(buildDashboardHref("reference"));
      return;
    }

    router.push(buildReferenceStyleHref(creative.id));
  }

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function goTo(nextStep: ReferenceStyleStep) {
    router.push(buildReferenceStyleHref(creative.id, nextStep));
  }

  function startChatFlow() {
    router.push(buildDashboardHref("chat"));
  }

  if (step === "analysis") {
    return (
      <>
        <StepHeader title="AI 스타일 분석" canGoBack onBack={goBack} onHome={goHome} />

        <section className={styles.styleInsightHero}>
          <Sparkles size={18} aria-hidden="true" />
          <div>
            <strong>AI가 선택한 레퍼런스를 분석했어요!</strong>
            <p>이 스타일을 참고해 내 가게 광고를 만들 수 있어요.</p>
          </div>
        </section>

        <section className={styles.styleAnalysisList} aria-label="AI 스타일 분석 결과">
          <StyleInsight icon={Palette} title="색감" copy="크림톤 베이스에 코랄 포인트를 사용해 따뜻하고 부드러운 느낌을 줘요.">
            <span className={styles.styleSwatches} aria-label="스타일 색상">
              {styleProfile.colors.map((color) => (
                <i key={color} style={{ background: color }} />
              ))}
            </span>
          </StyleInsight>
          <StyleInsight icon={Search} title="구도" copy={styleProfile.layout} />
          <StyleInsight icon={Type} title="카피 공간" copy={styleProfile.copySpace} />
          <StyleInsight icon={Heart} title="분위기" copy={styleProfile.mood} />
          <StyleInsight icon={Sparkles} title="추천 사용처" copy={styleProfile.bestUse} />
        </section>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={() => goTo("start")}>
            이 스타일로 내 광고 만들기
          </button>
          <button className={styles.secondaryButton} type="button" onClick={() => goTo("similar")}>
            비슷한 스타일 더 탐색하기
          </button>
        </div>
      </>
    );
  }

  if (step === "similar") {
    return (
      <>
        <StepHeader title="비슷한 스타일 추천" canGoBack onBack={goBack} onHome={goHome} />

        <p className={styles.styleIntroText}>이 스타일과 비슷한 레퍼런스를 추천해드려요.</p>
        <div className={styles.categoryScroller} aria-label="유사 스타일 카테고리">
          {similarCategories.map((category) => (
            <button className={category === "전체" ? styles.categoryActive : undefined} key={category} type="button">
              {category}
            </button>
          ))}
        </div>

        <section className={styles.referenceGrid} aria-label="비슷한 스타일 레퍼런스">
          {similarCreatives.map((item) => (
            <AdCreativeCard
              creative={item}
              key={item.id}
              onOpen={() => router.push(buildReferenceStyleHref(item.id))}
              onSave={() => undefined}
            />
          ))}
        </section>

        <button className={styles.savedReferenceBar} type="button" onClick={() => goTo("detail")}>
          <Heart size={18} aria-hidden="true" />
          <span>
            <strong>저장한 레퍼런스</strong>
            <small>{creative.savedCount ?? 12}개</small>
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={() => goTo("start")}>
            이 스타일로 내 광고 만들기
          </button>
        </div>
      </>
    );
  }

  if (step === "start") {
    return (
      <>
        <StepHeader title="이 스타일로 시작하기" canGoBack onBack={goBack} onHome={goHome} />

        <section className={styles.selectedStyleCard} aria-label="선택한 스타일">
          <div className={styles.selectedStyleVisual} data-tone={creative.tone} aria-hidden="true">
            <span />
          </div>
          <div>
            <small>선택한 스타일</small>
            <h2>{creative.title}</h2>
            <div className={styles.inlineTags}>
              {tags.slice(0, 3).map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          </div>
        </section>

        <p className={styles.styleNotice}>
          <Sparkles size={17} aria-hidden="true" />
          AI가 이 스타일을 참고해 브리프를 변환할 거예요. 이제 우리 가게 정보를 알려주세요.
        </p>

        <h2 className={styles.sectionTitle}>어떤 가게의 광고인가요?</h2>
        <div className={styles.styleBusinessGrid}>
          {businessTypes.map(({ label, icon: Icon }) => (
            <button data-active={businessType === label ? "true" : undefined} key={label} type="button" onClick={() => setBusinessType(label)}>
              <Icon size={16} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>

        <label className={styles.styleInputField}>
          <span>가게 이름</span>
          <input aria-label="가게 이름" placeholder="예) 도민 카페" value={businessName} onChange={(event) => setBusinessName(event.target.value)} />
        </label>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={startChatFlow}>
            다음
          </button>
          <button className={styles.secondaryButton} type="button" onClick={startChatFlow}>
            대화로 직접 입력하기 <PenLine size={17} aria-hidden="true" />
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className={styles.styleTopNav}>
        <button aria-label="레퍼런스 목록으로" type="button" onClick={goBack}>
          <ChevronRight size={22} aria-hidden="true" />
        </button>
        <h1>레퍼런스 상세</h1>
        <div>
          <button aria-label="공유하기" type="button">
            <Share2 size={18} aria-hidden="true" />
          </button>
          <button aria-label="더보기" type="button">
            <MoreHorizontal size={20} aria-hidden="true" />
          </button>
        </div>
      </div>

      <section className={styles.referenceDetailHero} data-tone={creative.tone} aria-label={`${creative.title} 상세 미리보기`}>
        <button aria-label={`${creative.title} 저장`} type="button">
          <Bookmark size={19} aria-hidden="true" />
        </button>
        <div>
          <strong>{creative.subtitle}</strong>
          <small>{creative.badge ?? creative.format}</small>
        </div>
        <span aria-hidden="true" />
      </section>

      <div className={styles.inlineTags}>
        {tags.slice(0, 5).map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>

      <div className={styles.referenceActionGrid}>
        <button type="button">
          <Heart size={18} aria-hidden="true" />
          <strong>저장</strong>
          <small>{creative.savedCount ?? 12}</small>
        </button>
        <button type="button">
          <Bookmark size={18} aria-hidden="true" />
          <strong>컬렉션에 저장</strong>
        </button>
        <button type="button">
          <MoreHorizontal size={18} aria-hidden="true" />
          <strong>더보기</strong>
        </button>
      </div>

      <p className={styles.styleNotice}>
        <Sparkles size={17} aria-hidden="true" />
        AI가 이 레퍼런스의 스타일을 분석해서 내 광고에 맞게 변형해드릴게요.
      </p>

      <div className={styles.stepFooter}>
        <button className={styles.primaryButton} type="button" onClick={() => goTo("analysis")}>
          이 스타일로 내 광고 만들기 <Sparkles size={18} aria-hidden="true" />
        </button>
        <button className={styles.secondaryButton} type="button" onClick={() => goTo("similar")}>
          비슷한 스타일 더 보기
        </button>
      </div>
    </>
  );
}

type StyleInsightProps = {
  icon: LucideIcon;
  title: string;
  copy: string;
  children?: ReactNode;
};

function StyleInsight({ icon: Icon, title, copy, children }: StyleInsightProps) {
  return (
    <article className={styles.styleInsightCard}>
      <span>
        <Icon size={19} aria-hidden="true" />
      </span>
      <div>
        <h2>{title}</h2>
        <p>{copy}</p>
        {children}
      </div>
    </article>
  );
}
