"use client";

import { useEffect, useMemo, useState } from "react";
import { Briefcase, CheckCircle2, ChevronLeft, Home, Search, Sparkles, User } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { fetchReferences } from "@/lib/api-client";
import { saveGenerationRequestContext } from "@/lib/generation-request-context";
import { referenceCreatives } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
import styles from "./generate.module.css";

type ReferenceTemplateCard = {
  template_id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  ad_formats?: string[];
  thumbnail_url?: string | null;
  preview_url?: string | null;
  style_keywords?: string[];
  tags?: string[];
};

type ReferenceListResponse = {
  success?: boolean;
  items?: ReferenceTemplateCard[];
};

type ReferenceBrowseStepProps = {
  state: ChatFlowState;
  progress: number;
  onShowProgress: () => void;
  isGenerationComplete?: boolean;
  isStandaloneGallery?: boolean;
  onGoHome?: () => void;
  onOpenReference?: () => void;
  onOpenStudio?: () => void;
  onOpenRecentAds?: () => void;
  onOpenBrandKit?: () => void;
  onSaveCreative?: (title: string) => void;
  onOpenCreative?: (creativeId: string) => void;
};

const categories = ["전체", "카페", "음식점", "뷰티", "포스터", "스토리"];

export function ReferenceBrowseStep({
  state,
  progress,
  onShowProgress,
  isGenerationComplete = false,
  isStandaloneGallery = false,
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenRecentAds,
  onOpenBrandKit,
  onSaveCreative,
  onOpenCreative
}: ReferenceBrowseStepProps) {
  const brief = buildBrief(state);
  const safeProgress = isGenerationComplete ? 100 : Math.max(12, Math.min(progress, 99));
  const [referenceTemplates, setReferenceTemplates] = useState<ReferenceTemplateCard[]>([]);
  const [referenceStatus, setReferenceStatus] = useState<"idle" | "loading" | "error">("idle");

  useEffect(() => {
    let cancelled = false;
    setReferenceStatus("loading");
    fetchReferences({ limit: 12 })
      .then((response) => {
        if (cancelled) {
          return;
        }
        const items = (response as ReferenceListResponse).items ?? [];
        setReferenceTemplates(items);
        setReferenceStatus("idle");
      })
      .catch(() => {
        if (!cancelled) {
          setReferenceStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const referenceCards = useMemo(() => {
    if (!referenceTemplates.length) {
      return referenceCreatives.map((item) => ({ creative: item, template: null as ReferenceTemplateCard | null }));
    }
    return referenceTemplates.map((template, index) => ({
      template,
      creative: {
        id: template.template_id,
        title: template.title,
        subtitle: template.description || template.style_keywords?.join(" · ") || template.category || "Reference template",
        format: template.ad_formats?.[0] || "instagram_feed",
        imageUrl: template.thumbnail_url || template.preview_url || null,
        tone: (["strawberry", "mint", "cream", "sunny", "peach"] as const)[index % 5],
        badge: template.category || "Reference",
        tags: template.tags || template.style_keywords || []
      }
    }));
  }, [referenceTemplates]);

  function selectReferenceTemplate(template: ReferenceTemplateCard | null, fallbackTitle: string) {
    if (template) {
      saveGenerationRequestContext({
        selectedReferenceTemplateId: template.template_id,
        selectedReferenceTemplateTitle: template.title,
        draftPrompt: `${template.title} 스타일로 광고를 만들고 싶어요.`,
        source: "reference_gallery"
      });
      onOpenStudio?.();
      return;
    }
    onOpenCreative?.(fallbackTitle);
  }

  return (
    <>
      {isStandaloneGallery ? (
        <div className={styles.galleryTopBar}>
          <button aria-label="홈으로" type="button" onClick={onGoHome}>
            <ChevronLeft size={22} aria-hidden="true" />
          </button>
          <span>REFERENCE GALLERY</span>
          <Search size={21} aria-hidden="true" />
        </div>
      ) : (
        <div className={styles.progressBanner} data-complete={isGenerationComplete}>
          {isGenerationComplete ? (
            <CheckCircle2 size={15} aria-hidden="true" />
          ) : (
            <span className={styles.spinnerDot} />
          )}
          <strong>
            {isGenerationComplete ? `${brief.item} 광고 생성 완료` : `${brief.item} 광고 생성 중 · ${safeProgress}%`}
          </strong>
          <span>{isGenerationComplete ? "비슷한 스타일을 둘러보세요" : `약 ${Math.max(5, Math.ceil((100 - safeProgress) / 4))}초 남음`}</span>
          <button type="button" onClick={onShowProgress}>
            {isGenerationComplete ? "결과로 돌아가기" : "진행 상황 보기"}
          </button>
        </div>
      )}

      <header className={styles.referenceHeader}>
        <div>
          <p>샘플 레퍼런스</p>
          <h1>찰떡 레퍼런스 둘러보기</h1>
        </div>
        {isStandaloneGallery ? null : <Search size={22} aria-hidden="true" />}
      </header>

      <p className={styles.sampleNotice}>
        {referenceStatus === "loading"
          ? "레퍼런스 템플릿을 불러오는 중이에요."
          : referenceStatus === "error"
            ? "레퍼런스 API 연결에 실패해 샘플 목록을 표시합니다."
            : referenceTemplates.length
              ? "원하는 레퍼런스를 선택하면 해당 스타일이 생성 요청에 반영됩니다."
              : "사용 가능한 레퍼런스가 없어 샘플 목록을 표시합니다."}
      </p>
      <label className={styles.searchField}>
        <Search size={17} aria-hidden="true" />
        <input aria-label="레퍼런스 검색어" placeholder="검색어를 입력하세요" />
      </label>

      <div className={styles.categoryScroller} aria-label="레퍼런스 카테고리">
        {categories.map((category) => (
          <button className={category === "전체" ? styles.categoryActive : undefined} key={category} type="button">
            {category}
          </button>
        ))}
      </div>

      <section className={styles.referenceGrid} aria-label="광고 레퍼런스 목록">
        {referenceCards.map(({ creative, template }) => (
          <AdCreativeCard
            creative={creative}
            key={creative.id}
            onOpen={() => selectReferenceTemplate(template, String(creative.id))}
            onSave={() => onSaveCreative?.(creative.title)}
          />
        ))}
      </section>

      <p className={styles.browseNote}>
        <Sparkles size={17} aria-hidden="true" />
        {isStandaloneGallery
          ? "레퍼런스를 고른 뒤 대화로 부족한 정보를 채우면 더 빠르게 광고를 만들 수 있어요."
          : isGenerationComplete
          ? "완성된 광고와 비슷한 톤의 레퍼런스를 더 둘러볼 수 있어요."
          : "광고가 완성되면 알려드릴게요. 기다리는 동안 다른 스타일을 둘러볼 수 있어요."}
      </p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button data-active={isStandaloneGallery ? undefined : "true"} type="button" onClick={onGoHome}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button data-active={isStandaloneGallery ? "true" : undefined} type="button" onClick={onOpenReference}>
          <Search size={18} aria-hidden="true" />
          레퍼런스
        </button>
        <button type="button" onClick={onOpenStudio}>
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button type="button" onClick={onOpenRecentAds}>
          <Briefcase size={18} aria-hidden="true" />
          보관함
        </button>
        <button type="button" onClick={onOpenBrandKit}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
