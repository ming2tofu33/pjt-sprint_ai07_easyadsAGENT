"use client";

import { Bell, Bookmark, Briefcase, Home, MoreHorizontal, Search, SlidersHorizontal, Sparkles, Star, User } from "lucide-react";
import { archivedCreatives, type CreativeTone, type MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type RecentAdsStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenBrandKit: () => void;
  onRegenerate: () => void;
  onShowProgress: () => void;
  onOpenAd: (creativeId: string) => void;
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
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenBrandKit,
  onRegenerate,
  onShowProgress,
  onOpenAd,
  onOpenNotifications
}: RecentAdsStepProps) {
  return (
    <>
      <header className={styles.recentHeader}>
        <button aria-label="알림" type="button" onClick={onOpenNotifications}>
          <Bell size={20} aria-hidden="true" />
        </button>
        <h1>내 찰떡 광고</h1>
        <Search size={21} aria-hidden="true" />
      </header>

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

      <section className={styles.archiveGrid} aria-label="내 광고 보관함">
        {archivedCreatives.map((ad) => (
          <article className={styles.archiveCard} key={ad.id}>
            <button aria-label={`${ad.title} 다시 보기`} className={`${styles.archiveVisual} ${styles[toneClassByCreativeTone[ad.tone]]}`} type="button" onClick={() => onOpenAd(ad.id)}>
              <span data-status={ad.status ?? "saved"}>{getStatusLabel(ad)}</span>
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
              <div>
                <button aria-label={`${ad.title} 즐겨찾기`} type="button">
                  <Star size={16} aria-hidden="true" />
                </button>
                <button aria-label={`${ad.title} 더보기`} type="button" onClick={() => ad.status === "generating" ? onShowProgress() : onRegenerate()}>
                  <MoreHorizontal size={17} aria-hidden="true" />
                </button>
              </div>
            </div>
          </article>
        ))}
      </section>

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
