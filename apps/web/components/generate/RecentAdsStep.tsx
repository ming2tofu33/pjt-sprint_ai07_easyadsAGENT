"use client";

import { Bell, Briefcase, Home, MoreHorizontal, Search, Smile, Sparkles, User } from "lucide-react";
import { recentCreatives, type CreativeTone } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type RecentAdsStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenBrandKit: () => void;
  onRegenerate: () => void;
  onShowProgress: () => void;
  onOpenAd: (title: string) => void;
};

const toneClassByCreativeTone: Record<CreativeTone, string> = {
  strawberry: "referenceTonepink",
  mint: "referenceTonemint",
  cream: "referenceTonecream",
  sunny: "referenceTonecream",
  peach: "referenceTonecoral"
};

export function RecentAdsStep({
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenBrandKit,
  onRegenerate,
  onShowProgress,
  onOpenAd
}: RecentAdsStepProps) {
  return (
    <>
      <header className={styles.recentHeader}>
        <button aria-label="알림" type="button">
          <Bell size={20} aria-hidden="true" />
        </button>
        <h1>내 찰떡 광고</h1>
        <Search size={21} aria-hidden="true" />
      </header>

      <section className={styles.generatingCard}>
        <h2>생성 중인 광고</h2>
        <div className={styles.inProgressAd}>
          <div className={`${styles.smallCreative} ${styles.referenceTonepink}`} />
          <div>
            <strong>딸기라떼 신메뉴 광고</strong>
            <p>인스타 피드 (1:1)</p>
            <span className={styles.inlineProgress}>
              <span style={{ width: "68%" }} />
            </span>
            <small>
              생성 중... 잠시만 기다려주세요 <Smile size={12} aria-hidden="true" />
            </small>
            <button className={styles.statusButton} type="button" onClick={onShowProgress}>
              진행 상황 보기
            </button>
          </div>
          <strong className={styles.percentText}>68%</strong>
        </div>
      </section>

      <section className={styles.recentListSection}>
        <div className={styles.sectionRow}>
          <h2>최근 만든 광고</h2>
          <button type="button">전체 보기 ›</button>
        </div>
        <div className={styles.recentAdList}>
          {recentCreatives.map((ad) => (
            <article className={styles.recentAdItem} key={ad.title}>
              <div className={`${styles.smallCreative} ${styles[toneClassByCreativeTone[ad.tone]]}`} />
              <div>
                <strong>{ad.title}</strong>
                <p>{ad.subtitle} · {ad.date}</p>
                <div>
                  <button type="button" onClick={() => onOpenAd(ad.title)}>다시 보기</button>
                  <button type="button" onClick={onRegenerate}>비슷하게 만들기</button>
                </div>
              </div>
              <MoreHorizontal size={20} aria-hidden="true" />
            </article>
          ))}
        </div>
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
