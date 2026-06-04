"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bell, Bookmark, Briefcase, Download, Eye, Home, MoreHorizontal, RefreshCcw, Search, SlidersHorizontal, Sparkles, Star, Trash2, User, X } from "lucide-react";
import Image from "next/image";
import { archivedCreatives, type CreativeTone, type MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type RecentAdsStepProps = {
  generatedCreatives?: MockCreative[];
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenBrandKit: () => void;
  onRegenerate: () => void;
  onShowProgress: () => void;
  onOpenGeneratedAd: (creativeId: string) => void;
  onOpenAd: (creativeId: string) => void;
  onDownloadGeneratedAd: (title: string) => void;
  onDeleteGeneratedAd: (creativeId: string, title: string) => void;
  onDeleteSampleAd: (title: string) => void;
  onOpenNotifications: () => void;
};

const toneClassByCreativeTone: Record<CreativeTone, string> = {
  strawberry: "referenceTonepink",
  mint: "referenceTonemint",
  cream: "referenceTonecream",
  sunny: "referenceTonecream",
  peach: "referenceTonecoral"
};

const filters = ["전체", "생성 중", "저장됨", "즐겨찾기"];

function matchesArchiveSearch(creative: MockCreative, query: string) {
  if (!query) {
    return true;
  }
  return [
    creative.title,
    creative.subtitle,
    creative.channel,
    creative.format,
    creative.date,
    creative.storage,
    ...(creative.tags ?? [])
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function getStatusLabel(creative: MockCreative) {
  if (creative.status === "generating") {
    return "생성 중";
  }
  if (creative.status === "favorite") {
    return "즐겨찾기";
  }
  if (creative.status === "draft") {
    return "삭제";
  }
  return "저장됨";
}

export function RecentAdsStep({
  generatedCreatives = [],
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenBrandKit,
  onRegenerate,
  onShowProgress,
  onOpenGeneratedAd,
  onOpenAd,
  onDownloadGeneratedAd,
  onDeleteGeneratedAd,
  onDeleteSampleAd,
  onOpenNotifications
}: RecentAdsStepProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [hiddenSampleIds, setHiddenSampleIds] = useState<string[]>([]);
  const [showSampleLibrary, setShowSampleLibrary] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const sampleCreatives = useMemo(
    () => archivedCreatives.filter((creative) => !hiddenSampleIds.includes(creative.id)),
    [hiddenSampleIds]
  );
  const normalizedSearchTerm = searchTerm.trim().toLowerCase();
  const filteredGeneratedCreatives = useMemo(
    () => generatedCreatives.filter((creative) => matchesArchiveSearch(creative, normalizedSearchTerm)),
    [generatedCreatives, normalizedSearchTerm]
  );
  const filteredSampleCreatives = useMemo(
    () => sampleCreatives.filter((creative) => matchesArchiveSearch(creative, normalizedSearchTerm)),
    [sampleCreatives, normalizedSearchTerm]
  );
  const hasActiveSearch = normalizedSearchTerm.length > 0;

  useEffect(() => {
    if (isSearchOpen) {
      searchInputRef.current?.focus();
    }
  }, [isSearchOpen]);

  function closeMenu() {
    setOpenMenuId(null);
  }

  function openSearch() {
    setIsSearchOpen(true);
  }

  function closeSearch() {
    setSearchTerm("");
    setIsSearchOpen(false);
  }

  return (
    <>
      <header className={styles.recentHeader}>
        <button aria-label="알림" type="button" onClick={onOpenNotifications}>
          <Bell size={20} aria-hidden="true" />
        </button>
        <h1>내 찰떡 광고</h1>
        <button aria-label={isSearchOpen ? "보관함 검색 닫기" : "보관함 검색 열기"} type="button" onClick={isSearchOpen ? closeSearch : openSearch}>
          <Search size={21} aria-hidden="true" />
        </button>
      </header>

      {isSearchOpen ? (
        <div className={`${styles.searchField} ${styles.archiveSearchField}`}>
          <Search size={17} aria-hidden="true" />
          <input
            ref={searchInputRef}
            aria-label="보관함 검색어"
            placeholder="광고 제목, 채널, 태그로 검색해보세요"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                closeSearch();
              }
            }}
          />
          {searchTerm ? (
            <button aria-label="보관함 검색어 지우기" className={styles.archiveSearchClear} type="button" onClick={() => setSearchTerm("")}>
              <X size={16} aria-hidden="true" />
            </button>
          ) : (
            <span aria-hidden="true" />
          )}
        </div>
      ) : null}

      <div className={styles.archiveFilterRow} aria-label="보관함 필터">
        {filters.map((filter) => (
          <button className={filter === "전체" ? styles.categoryActive : undefined} key={filter} type="button">
            {filter}
          </button>
        ))}
        <button aria-label="필터 설정" type="button">
          <SlidersHorizontal size={18} aria-hidden="true" />
        </button>
      </div>

      {generatedCreatives.length > 0 ? (
        <>
          <h2 className={styles.archiveSectionTitle}>최근 실제 생성</h2>
          {filteredGeneratedCreatives.length > 0 ? (
            <section className={styles.archiveGrid} aria-label="최근 실제 생성 광고">
              {filteredGeneratedCreatives.map((ad) => (
                <ArchiveCard
                  ad={ad}
                  isGenerated
                  key={ad.id}
                  menuOpen={openMenuId === ad.id}
                  onDelete={() => {
                    closeMenu();
                    onDeleteGeneratedAd(ad.id, ad.title);
                  }}
                  onDownload={() => onDownloadGeneratedAd(ad.title)}
                  onOpen={() => onOpenGeneratedAd(ad.id)}
                  onRegenerate={onRegenerate}
                  onToggleMenu={() => setOpenMenuId((current) => (current === ad.id ? null : ad.id))}
                />
              ))}
            </section>
          ) : (
            <section className={styles.emptyResultPanel} aria-label="최근 실제 생성 검색 결과 없음">
              <Search size={24} aria-hidden="true" />
              <strong>검색 결과가 없어요</strong>
              <p>다른 광고 제목이나 채널명으로 다시 찾아보세요.</p>
            </section>
          )}
        </>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="실제 생성 광고 없음">
          <Briefcase size={24} aria-hidden="true" />
          <strong>{hasActiveSearch ? "검색할 실제 생성 결과가 없어요" : "아직 저장된 실제 생성 결과가 없어요"}</strong>
          <p>
            {hasActiveSearch
              ? "실제 완성된 이미지가 생기면 제목이나 채널명으로 찾아볼 수 있어요."
              : "대화나 사진으로 광고를 만들면 실제 완성된 이미지 결과만 이 브라우저의 최근 결과에 표시됩니다."}
          </p>
          {hasActiveSearch ? null : (
            <button className={styles.secondaryButton} type="button" onClick={onOpenStudio}>
              새 광고 만들기
            </button>
          )}
        </section>
      )}

      <div className={styles.sampleLibraryHeader}>
        <h2 className={styles.archiveSectionTitle}>샘플 광고</h2>
        <button type="button" onClick={() => setShowSampleLibrary((current) => !current)}>
          {showSampleLibrary ? "숨기기" : "보기"}
        </button>
      </div>
      <p className={styles.sampleNotice}>
        아래 항목은 실제 생성 결과가 아니라 화면 확인용 샘플입니다. 보관함의 실제 결과와 분리해서 표시합니다.
      </p>
      {showSampleLibrary && filteredSampleCreatives.length > 0 ? (
        <section className={styles.archiveGrid} aria-label="샘플 광고 보관함">
          {filteredSampleCreatives.map((ad) => (
            <ArchiveCard
              ad={ad}
              key={ad.id}
              menuOpen={openMenuId === ad.id}
              onDelete={() => {
                closeMenu();
                setHiddenSampleIds((current) => [...current, ad.id]);
                onDeleteSampleAd(ad.title);
              }}
              onOpen={() => onOpenAd(ad.id)}
              onRegenerate={ad.status === "generating" ? onShowProgress : onRegenerate}
              onShowProgress={onShowProgress}
              onToggleMenu={() => setOpenMenuId((current) => (current === ad.id ? null : ad.id))}
            />
          ))}
        </section>
      ) : null}
      {showSampleLibrary && filteredSampleCreatives.length === 0 ? (
        <section className={styles.emptyResultPanel} aria-label="샘플 광고 검색 결과 없음">
          <Search size={24} aria-hidden="true" />
          <strong>샘플 광고 검색 결과가 없어요</strong>
          <p>다른 키워드로 다시 검색해보세요.</p>
        </section>
      ) : null}

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={onGoHome}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={onOpenReference}>
          <Search size={18} aria-hidden="true" />
          레퍼런스
        </button>
        <button type="button" onClick={onOpenStudio}>
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button data-active="true" type="button">
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

function ArchiveCard({
  ad,
  isGenerated = false,
  menuOpen,
  onDelete,
  onDownload,
  onOpen,
  onRegenerate,
  onShowProgress,
  onToggleMenu
}: {
  ad: MockCreative;
  isGenerated?: boolean;
  menuOpen: boolean;
  onDelete: () => void;
  onDownload?: () => void;
  onOpen: () => void;
  onRegenerate: () => void;
  onShowProgress?: () => void;
  onToggleMenu: () => void;
}) {
  const hasImage = Boolean(ad.imageUrl);
  const isGenerating = ad.status === "generating";
  const viewLabel = isGenerated ? "결과 보기" : isGenerating ? "진행 상황 보기" : "보기";
  function runMenuAction(action: () => void) {
    onToggleMenu();
    action();
  }

  return (
    <article className={styles.archiveCard}>
      <button
        aria-label={`${ad.title} ${isGenerated ? "실제 생성 결과 보기" : "다시 보기"}`}
        className={`${styles.archiveVisual} ${styles[toneClassByCreativeTone[ad.tone]]}`}
        data-has-image={hasImage ? "true" : undefined}
        type="button"
        onClick={onOpen}
      >
        {hasImage ? (
          <Image alt="" className={styles.archiveImage} fill sizes="170px" src={ad.imageUrl!} unoptimized />
        ) : null}
        <span data-status={ad.status ?? "saved"}>{isGenerated ? "실제 생성" : getStatusLabel(ad)}</span>
        <Bookmark size={17} aria-hidden="true" />
        {ad.progress ? (
          <small className={styles.archiveProgress}>
            <i style={{ width: `${ad.progress}%` }} />
            {ad.progress}%
          </small>
        ) : null}
      </button>
      <div className={styles.archiveCopy}>
        <strong>{ad.title}</strong>
        <p>{ad.channel ?? ad.format} · {ad.date ?? "2024.05.29"}</p>
        <div className={styles.archiveInlineActions}>
          <button aria-label={`${ad.title} 즐겨찾기`} type="button">
            <Star size={16} aria-hidden="true" />
          </button>
          <button aria-expanded={menuOpen} aria-haspopup="menu" aria-label={`${ad.title} 더보기`} type="button" onClick={onToggleMenu}>
            <MoreHorizontal size={17} aria-hidden="true" />
          </button>
        </div>
        {menuOpen ? (
          <div className={styles.archiveActionMenu} role="menu" aria-label={`${ad.title} 작업 메뉴`}>
            <button role="menuitem" type="button" onClick={() => runMenuAction(isGenerating && onShowProgress ? onShowProgress : onOpen)}>
              <Eye size={15} aria-hidden="true" />
              {viewLabel}
            </button>
            {!isGenerating ? (
              <button role="menuitem" type="button" onClick={() => runMenuAction(onRegenerate)}>
                <RefreshCcw size={15} aria-hidden="true" />
                비슷하게 만들기
              </button>
            ) : null}
            {isGenerated && !isGenerating && onDownload ? (
              <button role="menuitem" type="button" onClick={() => runMenuAction(onDownload)}>
                <Download size={15} aria-hidden="true" />
                다운로드
              </button>
            ) : null}
            <button className={styles.archiveDangerAction} role="menuitem" type="button" onClick={() => runMenuAction(onDelete)}>
              <Trash2 size={15} aria-hidden="true" />
              삭제
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}
