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
import styles from "./generate.module.css";

type HomeStartStepProps = {
  onOpenStudio: () => void;
  onOpenChat: () => void;
  onOpenReference: () => void;
  onOpenRecentAds: () => void;
  onOpenBrandKit: () => void;
};

export function HomeStartStep({
  onOpenStudio,
  onOpenChat,
  onOpenReference,
  onOpenRecentAds,
  onOpenBrandKit
}: HomeStartStepProps) {
  return (
    <>
      <header className={styles.dashboardHeader}>
        <h1>개떡찰떡</h1>
        <div>
          <button aria-label="알림" type="button">
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
          <p>대충 말해도 AI가 광고 브리프로 정리해드려요.</p>
          <button type="button" onClick={onOpenStudio}>
            광고 만들기 <Sparkles size={17} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.heroDog} aria-hidden="true">
          <span />
        </div>
      </section>

      <h2 className={styles.sectionTitle}>빠른 시작</h2>
      <div className={styles.quickDashboardGrid}>
        <button type="button" onClick={onOpenReference}>
          <span data-tone="lime">
            <ImageIcon size={24} aria-hidden="true" />
          </span>
          <strong>레퍼런스 보고 만들기</strong>
          <small>마음에 드는 광고 스타일을 골라요</small>
        </button>
        <button type="button">
          <span data-tone="purple">
            <Camera size={24} aria-hidden="true" />
          </span>
          <strong>내 사진으로 만들기</strong>
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
          <strong>브랜드 키트가 설정되어 있어요!</strong>
          <small>도민 카페 · 감성적인 · 크림/핑크톤</small>
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
