"use client";

import { Briefcase, CheckCircle2, ChevronLeft, Home, Search, Sparkles, User } from "lucide-react";
import { useState } from "react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { referenceCreatives } from "@/lib/mock-dashboard-data";
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
  const [showSampleReferences, setShowSampleReferences] = useState(false);

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

      <section className={styles.emptyResultPanel} aria-label="레퍼런스 API 연결 전">
        <Search size={24} aria-hidden="true" />
        <strong>아직 연결된 레퍼런스 결과가 없어요</strong>
        <p>레퍼런스 API가 연결되면 이 영역에 실제 검색 결과와 추천 스타일이 표시됩니다.</p>
        <button className={styles.secondaryButton} type="button" onClick={() => setShowSampleReferences((current) => !current)}>
          {showSampleReferences ? "샘플 레퍼런스 숨기기" : "샘플 레퍼런스 보기"}
        </button>
      </section>

      <label className={styles.searchField}>
        <Search size={17} aria-hidden="true" />
        <input aria-label="레퍼런스 검색어" placeholder="레퍼런스 API 연결 후 사용할 수 있어요" disabled />
      </label>

      {showSampleReferences ? (
        <>
          <p className={styles.sampleNotice}>
            아래 항목은 실제 검색 결과가 아니라 화면 확인용 샘플입니다. 실제 생성 결과와 분리해서 표시합니다.
          </p>

          <div className={styles.categoryScroller} aria-label="레퍼런스 카테고리">
            {categories.map((category) => (
              <button className={category === "전체" ? styles.categoryActive : undefined} key={category} type="button">
                {category}
              </button>
            ))}
          </div>

          <section className={styles.referenceGrid} aria-label="샘플 광고 레퍼런스 목록">
            {referenceCreatives.map((item) => (
              <AdCreativeCard creative={item} key={item.id} onOpen={() => onOpenCreative?.(item.id)} onSave={() => onSaveCreative?.(item.title)} />
            ))}
          </section>
        </>
      ) : null}

      <p className={styles.browseNote}>
        <Sparkles size={17} aria-hidden="true" />
        {isStandaloneGallery
          ? "실제 레퍼런스 연동 전까지는 생성 결과와 샘플 항목을 분리해 보여드려요."
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
