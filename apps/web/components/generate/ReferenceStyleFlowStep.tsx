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
import Image from "next/image";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchReferenceDetail, type ReferenceTemplateDetailResponse } from "@/lib/api-client";
import { readSavedBrandKit } from "@/lib/brand-kit-storage";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { clearGenerationDraftPrompt, saveGenerationRequestContext } from "@/lib/generation-request-context";
import {
  hasReferenceTemplateImage,
  referenceTemplateImageUrl,
  referenceTemplateToCreative
} from "@/lib/reference-template-creative";
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

export function ReferenceStyleFlowStep({ creativeId, step }: ReferenceStyleFlowStepProps) {
  const router = useRouter();
  const [detail, setDetail] = useState<ReferenceTemplateDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [businessType, setBusinessType] = useState("");
  const [businessName, setBusinessName] = useState("");
  const template = detail?.template ?? null;
  const creative = useMemo(() => (template ? referenceTemplateToCreative(template) : null), [template]);
  const similarCreatives = useMemo(
    () =>
      (detail?.similarTemplates ?? [])
        .filter(hasReferenceTemplateImage)
        .map((item) => referenceTemplateToCreative(item)),
    [detail]
  );
  const tags = useMemo(() => {
    if (!creative) {
      return [];
    }
    return creative.tags?.length ? creative.tags : [creative.format, creative.badge ?? ""].filter(Boolean);
  }, [creative]);
  const similarCategories = useMemo(() => uniqueLabels(["전체", ...tags.slice(0, 5)]), [tags]);
  const canContinue = Boolean(businessType && businessName.trim());

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);

    fetchReferenceDetail(creativeId)
      .then((response) => {
        if (!cancelled) {
          setDetail(response);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDetail(null);
          setErrorMessage(error instanceof Error ? error.message : "레퍼런스를 불러오지 못했어요.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [creativeId]);

  useEffect(() => {
    const savedBrandKit = readSavedBrandKit();
    if (!savedBrandKit) {
      return;
    }

    setBusinessType(savedBrandKit.businessType);
    setBusinessName(savedBrandKit.businessName);
  }, []);

  function goBack() {
    if (step === "detail") {
      router.push(buildDashboardHref("reference"));
      return;
    }

    router.push(buildReferenceStyleHref(creativeId));
  }

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function goTo(nextStep: ReferenceStyleStep) {
    router.push(buildReferenceStyleHref(creativeId, nextStep));
  }

  function buildStyleDraftPrompt(): string {
    return `${creative?.title ?? "선택한 레퍼런스"} 스타일로 ${businessName.trim()}의 ${businessType} 광고를 만들어줘`;
  }

  function startChatFlow() {
    if (!canContinue || !template) {
      return;
    }

    const draftPrompt = buildStyleDraftPrompt();
    saveGenerationRequestContext({
      selectedReferenceTemplateId: template.templateId,
      selectedReferenceTemplateTitle: template.title,
      draftPrompt,
      source: "manual"
    });
    router.push(buildDashboardHref("chat"));
  }

  function startBlankChatFlow() {
    clearGenerationDraftPrompt();
    router.push(buildDashboardHref("chat"));
  }

  if (isLoading) {
    return (
      <>
        <StepHeader title="레퍼런스 상세" canGoBack onBack={goBack} onHome={goHome} />
        <section className={styles.emptyResultPanel} aria-label="레퍼런스 불러오는 중">
          <Search size={24} aria-hidden="true" />
          <strong>레퍼런스를 불러오는 중이에요</strong>
          <p>선택한 스타일 정보를 확인하고 있어요.</p>
        </section>
      </>
    );
  }

  if (errorMessage || !creative || !template || !hasReferenceTemplateImage(template)) {
    return (
      <>
        <StepHeader title="레퍼런스 상세" canGoBack onBack={goBack} onHome={goHome} />
        <section className={styles.emptyResultPanel} aria-label="레퍼런스 상세 없음">
          <Search size={24} aria-hidden="true" />
          <strong>표시할 레퍼런스 이미지가 없어요</strong>
          <p>{errorMessage ?? "직접 넣은 이미지가 연결된 레퍼런스만 확인할 수 있어요."}</p>
          <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildDashboardHref("reference"))}>
            레퍼런스 목록으로
          </button>
        </section>
      </>
    );
  }

  const styleProfile = creative.styleProfile!;
  const imageUrl = referenceTemplateImageUrl(template)!;

  if (step === "analysis") {
    return (
      <>
        <StepHeader title="AI 스타일 분석" canGoBack onBack={goBack} onHome={goHome} />

        <section className={styles.styleInsightHero}>
          <Sparkles size={18} aria-hidden="true" />
          <div>
            <strong>선택한 레퍼런스 스타일을 정리했어요</strong>
            <p>이 스타일을 참고해 내 가게 광고를 만들 수 있어요.</p>
          </div>
        </section>

        <section className={styles.styleAnalysisList} aria-label="스타일 분석 결과">
          <StyleInsight icon={Palette} title="색감" copy="레퍼런스에 연결된 주요 색상을 광고 분위기 힌트로 사용해요.">
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

        <p className={styles.styleIntroText}>선택한 레퍼런스와 가까운 스타일을 모아봤어요.</p>
        <div className={styles.categoryScroller} aria-label="유사 스타일 태그">
          {similarCategories.map((category, index) => (
            <button className={index === 0 ? styles.categoryActive : undefined} key={category} type="button">
              {category}
            </button>
          ))}
        </div>

        {similarCreatives.length > 0 ? (
          <section className={styles.referenceGrid} aria-label="비슷한 스타일 레퍼런스">
            {similarCreatives.map((item) => (
              <AdCreativeCard
                creative={item}
                key={item.id}
                openLabel={`${item.title} 상세 보기`}
                openText="상세 보기"
                showPlaceholderArt={false}
                onOpen={() => router.push(buildReferenceStyleHref(item.id))}
              />
            ))}
          </section>
        ) : (
          <section className={styles.emptyResultPanel} aria-label="비슷한 스타일 없음">
            <Search size={24} aria-hidden="true" />
            <strong>비슷한 레퍼런스 이미지가 아직 없어요</strong>
            <p>이미지가 더 등록되면 가까운 스타일을 함께 보여드릴게요.</p>
          </section>
        )}

        <button className={styles.savedReferenceBar} type="button" onClick={() => goTo("detail")}>
          <Heart size={18} aria-hidden="true" />
          <span>
            <strong>비슷한 레퍼런스</strong>
            <small>{similarCreatives.length}개</small>
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
          <div className={styles.selectedStyleVisual} data-has-image="true">
            <Image alt="" className={styles.selectedStyleImage} fill sizes="112px" src={imageUrl} unoptimized />
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
          <input aria-label="가게 이름" placeholder="가게 이름을 입력하세요" value={businessName} onChange={(event) => setBusinessName(event.target.value)} />
        </label>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} disabled={!canContinue} type="button" onClick={startChatFlow}>
            다음
          </button>
          <button className={styles.secondaryButton} type="button" onClick={startBlankChatFlow}>
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

      <section className={styles.referenceDetailHero} data-has-image="true" aria-label={`${creative.title} 상세 미리보기`}>
        <Image alt="" className={styles.referenceDetailImage} fill sizes="360px" src={imageUrl} unoptimized />
        <button aria-label={`${creative.title} 저장`} type="button">
          <Bookmark size={19} aria-hidden="true" />
        </button>
        <div className={styles.referenceDetailOverlay}>
          <strong>{creative.title}</strong>
          <small>{creative.subtitle}</small>
        </div>
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
          <small>준비 중</small>
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

function uniqueLabels(labels: string[]): string[] {
  const seen = new Set<string>();
  return labels.filter((label) => {
    const trimmed = label.trim();
    if (!trimmed || seen.has(trimmed)) {
      return false;
    }
    seen.add(trimmed);
    return true;
  });
}
