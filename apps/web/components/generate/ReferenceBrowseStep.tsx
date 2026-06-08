"use client";

import { Bell, Briefcase, CheckCircle2, ChevronLeft, Home, Search, Sparkles, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { listReferenceTemplates, type ReferenceTemplateCard } from "@/lib/api-client";
import { generationStageViewFromJob } from "@/lib/generation-job-stage";
import { hasReferenceTemplateImage, referenceTemplateToCreative } from "@/lib/reference-template-creative";
import { AdCreativeCard } from "./AdCreativeCard";
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

type ReferenceBrowseStepProps = {
  state: ChatFlowState;
  onShowProgress: () => void;
  isGenerationComplete?: boolean;
  isStandaloneGallery?: boolean;
  onGoHome?: () => void;
  onOpenReference?: () => void;
  onOpenStudio?: () => void;
  onOpenRecentAds?: () => void;
  onOpenBrandKit?: () => void;
  onOpenNotifications?: () => void;
  onSaveCreative?: (title: string) => void;
  onOpenCreative?: (creativeId: string) => void;
  onUseTemplate?: (template: ReferenceTemplateCard) => void;
};

const categories = [
  { label: "전체", value: "" },
  { label: "카페", value: "cafe" },
  { label: "음식", value: "food" },
  { label: "뷰티", value: "beauty" },
  { label: "리테일", value: "retail" },
  { label: "스토리", value: "instagram_story" }
];

export function ReferenceBrowseStep({
  state,
  onShowProgress,
  isGenerationComplete = false,
  isStandaloneGallery = false,
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenRecentAds,
  onOpenBrandKit,
  onOpenNotifications,
  onSaveCreative,
  onOpenCreative,
  onUseTemplate
}: ReferenceBrowseStepProps) {
  const brief = buildBrief(state);
  const generationStage = generationStageViewFromJob(state.generationJob);
  const [templates, setTemplates] = useState<ReferenceTemplateCard[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const searchTags = useMemo(() => splitReferenceSearchTerms(searchTerm), [searchTerm]);
  const visibleTemplates = useMemo(
    () =>
      templates
        .filter(hasReferenceTemplateImage)
        .sort((first, second) => second.popularityScore - first.popularityScore),
    [templates]
  );

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);

    listReferenceTemplates({
      keyword: searchTerm,
      category: selectedCategory,
      tags: searchTags,
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
        setErrorMessage(error instanceof Error ? error.message : "샘플 목록을 불러오지 못했어요.");
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [searchTags, searchTerm, selectedCategory, reloadToken]);

  return (
    <>
      {isStandaloneGallery ? (
        <div className={styles.galleryTopBar}>
          <button aria-label="홈으로" type="button" onClick={onGoHome}>
            <ChevronLeft size={22} aria-hidden="true" />
          </button>
          <span>SAMPLE GALLERY</span>
          <button aria-label="알림" type="button" onClick={onOpenNotifications}>
            <Bell size={21} aria-hidden="true" />
          </button>
        </div>
      ) : (
        <div className={styles.progressBanner} data-complete={isGenerationComplete}>
          {isGenerationComplete ? (
            <CheckCircle2 size={15} aria-hidden="true" />
          ) : (
            <span className={styles.spinnerDot} />
          )}
          <strong>
            {isGenerationComplete ? `${brief.item} 광고 생성 완료` : `${brief.item} 광고 생성 중`}
          </strong>
          <span>{isGenerationComplete ? "비슷한 스타일을 둘러보세요" : generationStage.label}</span>
          <button type="button" onClick={onShowProgress}>
            {isGenerationComplete ? "결과로 돌아가기" : "진행 상황 보기"}
          </button>
        </div>
      )}

      <header className={styles.referenceHeader}>
        <div>
          <p>SAMPLE</p>
          <h1>찰떡 광고 샘플 둘러보기</h1>
        </div>
        {isStandaloneGallery ? null : (
          <button className={styles.iconButton} aria-label="알림" type="button" onClick={onOpenNotifications}>
            <Bell size={22} aria-hidden="true" />
          </button>
        )}
      </header>

      <label className={styles.searchField}>
        <Search size={17} aria-hidden="true" />
        <input
          aria-label="샘플 검색어"
          placeholder="음료, 여름, 포스터처럼 검색해보세요"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
      </label>

      <div className={styles.categoryScroller} aria-label="샘플 카테고리">
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

      <div className={styles.referenceContentScroll}>
        <p className={`${styles.browseNote} ${styles.referenceBrowseNote}`}>
          <Sparkles size={17} aria-hidden="true" />
          {isStandaloneGallery
            ? "마음에 드는 샘플을 고르면 생성할 광고 이미지에 반영돼요."
            : isGenerationComplete
            ? "완성된 광고와 비슷한 톤의 샘플을 더 둘러볼 수 있어요."
            : "광고가 완성되면 알려드릴게요. 기다리는 동안 다른 스타일을 둘러볼 수 있어요."}
        </p>

        {isLoading ? (
          <section className={styles.skeletonGrid} aria-label="샘플 목록 불러오는 중">
            {Array.from({ length: 4 }).map((_, index) => (
              <div className={styles.skeletonCreative} key={index}>
                <span />
              </div>
            ))}
          </section>
        ) : errorMessage ? (
          <section className={styles.emptyResultPanel} aria-label="샘플 불러오기 실패">
            <MascotImage role="errorWorried" decorative className={styles.emptyMascot} />
            <strong>샘플을 불러오지 못했어요</strong>
            <p>{errorMessage}</p>
            <button className={styles.secondaryButton} type="button" onClick={() => setReloadToken((current) => current + 1)}>
              다시 시도
            </button>
          </section>
        ) : visibleTemplates.length > 0 ? (
          <section className={styles.referenceGrid} aria-label="광고 샘플 목록">
            {visibleTemplates.map((template) => {
              const creative = referenceTemplateToCreative(template);
              return (
                <AdCreativeCard
                  creative={creative}
                  key={template.templateId}
                  savePlacement="copy"
                  showPlaceholderArt={false}
                  openOnImage
                  openLabel={`${template.title} 상세 보기`}
                  onOpen={() => {
                    if (onOpenCreative) {
                      onOpenCreative(template.templateId);
                      return;
                    }
                    onUseTemplate?.(template);
                  }}
                  onSave={() => onSaveCreative?.(template.title)}
                />
              );
            })}
          </section>
        ) : (
          <section className={styles.emptyResultPanel} aria-label="샘플 검색 결과 없음">
            <MascotImage role="referenceSearch" decorative className={styles.emptyMascot} />
            <strong>조건에 맞는 샘플 이미지가 없어요</strong>
            <p>직접 넣은 샘플 이미지가 연결되면 여기에 표시돼요.</p>
          </section>
        )}
      </div>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button data-active={isStandaloneGallery ? undefined : "true"} type="button" onClick={onGoHome}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button data-active={isStandaloneGallery ? "true" : undefined} type="button" onClick={onOpenReference}>
          <Search size={18} aria-hidden="true" />
          찾기
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

function splitReferenceSearchTerms(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(/[\s,，]+/)
    .map((term) => term.trim())
    .filter((term) => {
      if (!term || seen.has(term)) {
        return false;
      }
      seen.add(term);
      return true;
    });
}
