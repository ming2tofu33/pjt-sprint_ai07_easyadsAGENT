"use client";

import { Bell, Briefcase, Home, MoreHorizontal, Search, Sparkles, User } from "lucide-react";
import styles from "./generate.module.css";

type RecentAdsStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenBrandKit: () => void;
  onRegenerate: () => void;
};

const recentAds = [
  { title: "딸기라떼 신메뉴 광고", meta: "인스타 피드 (1:1) · 2024.05.29", tone: "pink" },
  { title: "카페 할인 이벤트", meta: "인스타 스토리 (9:16) · 2024.05.25", tone: "cream" },
  { title: "여름 시즌 포스터", meta: "포스터 (4:5) · 2024.05.20", tone: "mint" }
];

export function RecentAdsStep({ onGoHome, onOpenReference, onOpenStudio, onOpenBrandKit, onRegenerate }: RecentAdsStepProps) {
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
            <small>생성 중... 잠시만 기다려주세요 😊</small>
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
          {recentAds.map((ad) => (
            <article className={styles.recentAdItem} key={ad.title}>
              <div className={`${styles.smallCreative} ${styles[`referenceTone${ad.tone}`]}`} />
              <div>
                <strong>{ad.title}</strong>
                <p>{ad.meta}</p>
                <div>
                  <button type="button">다시 보기</button>
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
