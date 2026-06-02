"use client";

import { Briefcase, CheckCircle2, ChevronLeft, Home, Search, Sparkles, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { listReferenceTemplates, type ReferenceTemplateCard } from "@/lib/api-client";
import type { CreativeTone, MockCreative } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
import styles from "./generate.module.css";

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
  onUseTemplate?: (template: ReferenceTemplateCard) => void;
};

const categories = [
  { label: "전체", value: "" },
  { label: "카페", value: "cafe" },
  { label: "음식점", value: "restaurant" },
  { label: "뷰티", value: "beauty" },
  { label: "리테일", value: "retail" },
  { label: "스토리", value: "instagram_story" }
];

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
  onOpenCreative,
  onUseTemplate
}: ReferenceBrowseStepProps) {
  const brief = buildBrief(state);
  const safeProgress = isGenerationComplete ? 100 : Math.max(12, Math.min(progress, 99));
  const [templates, setTemplates] = useState<ReferenceTemplateCard[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const sortedTemplates = useMemo(
    () =>
      [...templates].sort((first, second) => {
        const firstHasImage = first.thumbnailUrl || first.previewUrl ? 1 : 0;
        const secondHasImage = second.thumbnailUrl || second.previewUrl ? 1 : 0;
        return secondHasImage - firstHasImage || second.popularityScore - first.popularityScore;
      }),
    [templates]
  );
  const hasTemporaryTemplates = sortedTemplates.some((template) => template.templateId.startsWith("temp_"));

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);

    listReferenceTemplates({
      keyword: searchTerm,
      category: selectedCategory,
      limit: 60
    })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setTemplates(response.items);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setTemplates([]);
        setErrorMessage(error instanceof Error ? error.message : "레퍼런스 목록을 불러오지 못했어요.");
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [searchTerm, selectedCategory, reloadToken]);

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
          <p>REFERENCE</p>
          <h1>찰떡 레퍼런스 둘러보기</h1>
        </div>
        {isStandaloneGallery ? null : <Search size={22} aria-hidden="true" />}
      </header>

      <label className={styles.searchField}>
        <Search size={17} aria-hidden="true" />
        <input
          aria-label="레퍼런스 검색어"
          placeholder="음료, 여름, 포스터처럼 검색해보세요"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
      </label>

      <div className={styles.categoryScroller} aria-label="레퍼런스 카테고리">
        {categories.map((category) => (
          <button
            className={selectedCategory === category.value ? styles.categoryActive : undefined}
            key={category.value || "all"}
            type="button"
            onClick={() => setSelectedCategory(category.value)}
          >
            {category.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <section className={styles.skeletonGrid} aria-label="레퍼런스 목록 불러오는 중">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className={styles.skeletonCreative} key={index}>
              <span />
            </div>
          ))}
        </section>
      ) : errorMessage ? (
        <section className={styles.emptyResultPanel} aria-label="레퍼런스 불러오기 실패">
          <Search size={24} aria-hidden="true" />
          <strong>레퍼런스를 불러오지 못했어요</strong>
          <p>{errorMessage}</p>
          <button className={styles.secondaryButton} type="button" onClick={() => setReloadToken((current) => current + 1)}>
            다시 시도
          </button>
        </section>
      ) : sortedTemplates.length > 0 ? (
        <>
          <p className={styles.sampleNotice}>
            {hasTemporaryTemplates
              ? "개발용 임시 레퍼런스가 포함되어 있어요. 선택하면 다음 생성 요청에 스타일 템플릿으로 반영됩니다."
              : "레퍼런스 API에서 불러온 스타일입니다. 선택하면 다음 생성 요청에 템플릿으로 반영됩니다."}
          </p>
          <section className={styles.referenceGrid} aria-label="광고 레퍼런스 목록">
            {sortedTemplates.map((template) => {
              const creative = referenceTemplateToCreative(template);
              return (
                <AdCreativeCard
                  creative={creative}
                  key={template.templateId}
                  openLabel={`${template.title} 스타일로 시작`}
                  onOpen={() => {
                    if (onUseTemplate) {
                      onUseTemplate(template);
                      return;
                    }
                    onOpenCreative?.(template.templateId);
                  }}
                  onSave={() => onSaveCreative?.(template.title)}
                />
              );
            })}
          </section>
        </>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="레퍼런스 검색 결과 없음">
          <Search size={24} aria-hidden="true" />
          <strong>조건에 맞는 레퍼런스가 없어요</strong>
          <p>검색어나 카테고리를 바꿔서 다시 찾아보세요.</p>
        </section>
      )}

      <p className={styles.browseNote}>
        <Sparkles size={17} aria-hidden="true" />
        {isStandaloneGallery
          ? "마음에 드는 레퍼런스를 고르면 다음 광고 생성 요청에 스타일 힌트로 함께 전달돼요."
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

function referenceTemplateToCreative(template: ReferenceTemplateCard): MockCreative {
  return {
    id: template.templateId,
    title: template.title,
    subtitle: template.description ?? [formatLabel(template), ...template.tags.slice(0, 2)].filter(Boolean).join(" · "),
    format: formatLabel(template),
    imageUrl: template.thumbnailUrl ?? template.previewUrl,
    tone: toneForTemplate(template),
    badge: template.templateId.startsWith("temp_") ? "임시 레퍼런스" : categoryLabel(template.category),
    tags: template.tags,
    savedCount: Math.round(template.popularityScore * 100),
    styleProfile: {
      colors: template.colorPalette.length > 0 ? template.colorPalette : ["#F7F4EF", "#111827", "#D1D5DB"],
      layout: template.layoutHint ?? "선택한 템플릿의 레이아웃 힌트를 생성 요청에 반영해요.",
      copySpace: template.typographyHint ?? "문구가 잘 읽히는 위치와 크기를 참고해요.",
      mood: template.styleKeywords.join(", ") || categoryLabel(template.category),
      bestUse: [formatLabel(template), ...template.businessTypes].filter(Boolean).join(", ")
    }
  };
}

function formatLabel(template: ReferenceTemplateCard): string {
  const format = template.adFormats[0] ?? template.aspectRatio ?? "reference";
  const labels: Record<string, string> = {
    instagram_feed: "인스타 피드",
    instagram_story: "인스타 스토리",
    poster: "포스터",
    flyer: "전단지",
    banner: "배너"
  };
  return labels[format] ?? format;
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    cafe: "카페",
    restaurant: "음식점",
    beauty: "뷰티",
    retail: "리테일",
    event: "이벤트",
    flyer: "전단지",
    banner: "배너",
    instagram_story: "스토리",
    instagram_feed: "피드"
  };
  return labels[category] ?? category;
}

function toneForTemplate(template: ReferenceTemplateCard): CreativeTone {
  const joined = [...template.styleKeywords, ...template.tags, template.category].join(" ").toLowerCase();
  if (joined.includes("mint") || joined.includes("clean") || joined.includes("green")) {
    return "mint";
  }
  if (joined.includes("yellow") || joined.includes("summer") || joined.includes("event")) {
    return "sunny";
  }
  if (joined.includes("purple") || joined.includes("premium") || joined.includes("minimal")) {
    return "cream";
  }
  if (joined.includes("strawberry") || joined.includes("pink") || joined.includes("dessert")) {
    return "strawberry";
  }
  return "peach";
}
