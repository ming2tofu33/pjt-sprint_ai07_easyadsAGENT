"use client";

import { Briefcase, Home, Palette, Search, Sparkles, Store, User } from "lucide-react";
import { brandFacts, referenceCreatives } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
import styles from "./generate.module.css";

type BrandKitStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenRecentAds: () => void;
  onEditBrandKit?: () => void;
};

export function BrandKitStep({
  onGoHome,
  onOpenReference,
  onOpenStudio,
  onOpenRecentAds,
  onEditBrandKit
}: BrandKitStepProps) {
  return (
    <>
      <header className={styles.brandKitHeader}>
        <h1>추천 & 브랜드 키트</h1>
      </header>

      <section className={styles.recommendSection}>
        <div className={styles.sectionRow}>
          <h2>오늘의 추천 레퍼런스</h2>
          <button type="button" onClick={onOpenReference}>더 보기 ›</button>
        </div>
        <div className={styles.recommendGrid}>
          {referenceCreatives.map((item) => (
            <AdCreativeCard compact creative={item} key={item.id} onSave={() => onOpenReference()} />
          ))}
        </div>
      </section>

      <section className={styles.brandProfileCard}>
        <div className={styles.sectionRow}>
          <h2>브랜드 키트</h2>
          <button type="button" onClick={onEditBrandKit}>수정하기 ›</button>
        </div>
        <div className={styles.brandIdentity}>
          <span>
            <Store size={28} aria-hidden="true" />
          </span>
          <div>
            <strong>{brandFacts.name}</strong>
            <small>{brandFacts.status}</small>
            <p>{brandFacts.meta}</p>
          </div>
        </div>
        <dl className={styles.brandFacts}>
          <div>
            <dt>브랜드 톤</dt>
            <dd>{brandFacts.tone}</dd>
          </div>
          <div>
            <dt>브랜드 컬러</dt>
            <dd>
              {brandFacts.colors.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </dd>
          </div>
          <div>
            <dt>대표 상품</dt>
            <dd>{brandFacts.products}</dd>
          </div>
          <div>
            <dt>자주 쓰는 문구</dt>
            <dd>{brandFacts.phrases}</dd>
          </div>
        </dl>
      </section>

      <p className={styles.brandKitNotice}>
        <Palette size={18} aria-hidden="true" />
        브랜드 키트가 적용된 광고는 더 찰떡같은 결과를 보여드려요!
      </p>

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
        <button type="button" onClick={onOpenRecentAds}>
          <Briefcase size={18} aria-hidden="true" />
          보관함
        </button>
        <button data-active="true" type="button">
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
