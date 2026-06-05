"use client";

import {
  Bell,
  Briefcase,
  Camera,
  ChevronRight,
  Grid3X3,
  Home,
  Image as ImageIcon,
  MessageCircle,
  Search,
  Sparkles,
  User
} from "lucide-react";
import { useEffect, useState } from "react";
import { brandKitMeta, brandKitTone, readSavedBrandKit, type StoredBrandKit } from "@/lib/brand-kit-storage";
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

type HomeStartStepProps = {
  onOpenStudio: () => void;
  onOpenChat: () => void;
  onOpenPhoto: () => void;
  onOpenReference: () => void;
  onOpenRecentAds: () => void;
  onOpenBrandKit: () => void;
  onOpenNotifications: () => void;
};

export function HomeStartStep({
  onOpenStudio,
  onOpenChat,
  onOpenPhoto,
  onOpenReference,
  onOpenRecentAds,
  onOpenBrandKit,
  onOpenNotifications
}: HomeStartStepProps) {
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);

  useEffect(() => {
    setBrandKit(readSavedBrandKit());
  }, []);

  return (
    <>
      <header className={styles.dashboardHeader}>
        <h1>개떡찰떡</h1>
        <div>
          <button aria-label="알림" type="button" onClick={onOpenNotifications}>
            <Bell size={19} aria-hidden="true" />
          </button>
          <button aria-label="프로필" type="button" onClick={onOpenBrandKit}>
            <User size={19} aria-hidden="true" />
          </button>
        </div>
      </header>

      <section className={styles.dashboardHero}>
        <div>
          <h2>
            오늘 어떤 광고를
            <br />
            만들어볼까요?
          </h2>
          <p>
            대충 말해도 AI가 광고 브리프로{" "}
            <br />
            정리해드려요.
          </p>
          <button type="button" onClick={onOpenStudio}>
            광고 만들기 <Sparkles size={17} aria-hidden="true" />
          </button>
        </div>
        <MascotImage role="homeReady" decorative priority className={styles.dashboardHeroMascot} />
      </section>

      <h2 className={styles.sectionTitle}>빠른 시작</h2>
      <div className={styles.quickDashboardGrid}>
        <button aria-label="레퍼런스 보고 만들기" type="button" onClick={onOpenReference}>
          <span data-tone="lime">
            <ImageIcon size={24} aria-hidden="true" />
          </span>
          <strong>
            레퍼런스 보고{" "}
            <br />
            만들기
          </strong>
          <small>
            마음에 드는 광고{" "}
            <br />
            스타일을 골라요
          </small>
        </button>
        <button aria-label="내 사진으로 만들기" type="button" onClick={onOpenPhoto}>
          <span data-tone="purple">
            <Camera size={24} aria-hidden="true" />
          </span>
          <strong>
            내 사진으로{" "}
            <br />
            만들기
          </strong>
          <small>사진을 올리면 AI가 제안해요</small>
        </button>
        <button type="button" onClick={onOpenChat}>
          <span data-tone="mint">
            <MessageCircle size={24} aria-hidden="true" />
          </span>
          <strong>대화로 시작하기</strong>
          <small>말로 설명하면 AI가 질문해요</small>
        </button>
      </div>

      <button className={styles.brandNoticeCard} type="button" onClick={onOpenBrandKit}>
        <span>
          <Grid3X3 size={22} aria-hidden="true" />
        </span>
        <div>
          <strong>{brandKit ? "브랜드 키트가 연결되어 있어요" : "브랜드 키트를 연결해보세요"}</strong>
          <small>{brandKit ? `${brandKit.businessName} · ${brandKitTone(brandKit)} · ${brandKitMeta(brandKit)}` : "가게 정보와 톤을 저장하면 광고 요청에 함께 반영돼요"}</small>
        </div>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button data-active="true" type="button">
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
        <button type="button" onClick={onOpenBrandKit}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
