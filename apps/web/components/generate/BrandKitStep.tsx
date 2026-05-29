"use client";

import { Briefcase, Home, Palette, Search, Sparkles, Store, User } from "lucide-react";
import styles from "./generate.module.css";

type BrandKitStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenRecentAds: () => void;
};

const recommendations = [
  { title: "감성 카페 신메뉴", tone: "cream" },
  { title: "리뷰 이벤트 배너", tone: "mint" },
  { title: "인스타 스토리", tone: "coral" },
  { title: "시즌 할인 포스터", tone: "pink" }
];

export function BrandKitStep({ onGoHome, onOpenReference, onOpenStudio, onOpenRecentAds }: BrandKitStepProps) {
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
          {recommendations.map((item) => (
            <article className={`${styles.recommendCard} ${styles[`referenceTone${item.tone}`]}`} key={item.title}>
              <div className={styles.miniCup} />
              <strong>{item.title}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.brandProfileCard}>
        <div className={styles.sectionRow}>
          <h2>브랜드 키트</h2>
          <button type="button">수정하기 ›</button>
        </div>
        <div className={styles.brandIdentity}>
          <span>
            <Store size={28} aria-hidden="true" />
          </span>
          <div>
            <strong>도민 카페</strong>
            <small>사용 중</small>
            <p>카페 · 성수동 감성 상권 · @domin_cafe</p>
          </div>
        </div>
        <dl className={styles.brandFacts}>
          <div>
            <dt>브랜드 톤</dt>
            <dd>감성적인, 따뜻한</dd>
          </div>
          <div>
            <dt>브랜드 컬러</dt>
            <dd>
              <span style={{ background: "#d7b48b" }} />
              <span style={{ background: "#ffd7c9" }} />
              <span style={{ background: "#d8a29b" }} />
            </dd>
          </div>
          <div>
            <dt>대표 상품</dt>
            <dd>딸기라떼, 바닐라라떼, 크림라떼</dd>
          </div>
          <div>
            <dt>자주 쓰는 문구</dt>
            <dd>신메뉴 출시, 매일 한정 수량, 예약은 DM</dd>
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
