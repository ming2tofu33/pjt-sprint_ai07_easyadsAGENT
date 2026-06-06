"use client";

import { Briefcase, Home, Palette, Search, Sparkles, Store, User } from "lucide-react";
import { useEffect, useState } from "react";
import {
  brandKitMeta,
  brandKitPhrases,
  brandKitProducts,
  brandKitTone,
  readSavedBrandKit,
  type StoredBrandKit
} from "@/lib/brand-kit-storage";
import { referenceCreatives } from "@/lib/mock-dashboard-data";
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
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);

  useEffect(() => {
    setBrandKit(readSavedBrandKit());
  }, []);

  return (
    <>
      <header className={styles.brandKitHeader}>
        <h1>추천 & 브랜드 파일</h1>
      </header>

      <section className={styles.recommendSection}>
        <div className={styles.sectionRow}>
          <h2>오늘의 추천 샘플</h2>
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
          <h2>브랜드 파일</h2>
          <button type="button" onClick={onEditBrandKit}>수정하기 ›</button>
        </div>
        <div className={styles.brandIdentity}>
          <span>
            <Store size={28} aria-hidden="true" />
          </span>
          <div>
            <strong>{brandKit?.businessName ?? "브랜드 파일 연결 전"}</strong>
            <small>{brandKit ? "저장됨" : "등록 전"}</small>
            <p>{brandKit ? brandKitMeta(brandKit) : "가게 정보를 입력하면 여기에 표시됩니다."}</p>
          </div>
        </div>
        <dl className={styles.brandFacts}>
          <div>
            <dt>브랜드 톤</dt>
            <dd>{brandKit ? brandKitTone(brandKit) : "브랜드 톤 선택 전"}</dd>
          </div>
          <div>
            <dt>브랜드 컬러</dt>
            <dd>
              {brandKit?.colors.length ? brandKit.colors.map((color) => <span key={color} style={{ background: color }} />) : "선택 전"}
            </dd>
          </div>
          <div>
            <dt>대표 상품</dt>
            <dd>{brandKit ? brandKitProducts(brandKit) : "대표 상품 선택 전"}</dd>
          </div>
          <div>
            <dt>자주 쓰는 문구</dt>
            <dd>{brandKit ? brandKitPhrases(brandKit) : "자주 쓰는 문구 선택 전"}</dd>
          </div>
        </dl>
      </section>

      <p className={styles.brandKitNotice}>
        <Palette size={18} aria-hidden="true" />
        {brandKit ? "브랜드 파일이 적용된 광고는 더 찰떡같은 결과를 보여드려요!" : "브랜드 파일을 저장하면 다음 광고 흐름에서 바로 확인할 수 있어요."}
      </p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={onGoHome}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={onOpenReference}>
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
        <button data-active="true" type="button">
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
