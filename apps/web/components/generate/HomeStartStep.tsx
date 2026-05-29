"use client";

import {
  Bell,
  Briefcase,
  ChevronRight,
  Grid3X3,
  Home,
  Image as ImageIcon,
  MessageCircle,
  Package,
  User
} from "lucide-react";
import styles from "./generate.module.css";

type HomeStartStepProps = {
  onOpenChat: () => void;
  onOpenReference: () => void;
};

export function HomeStartStep({ onOpenChat, onOpenReference }: HomeStartStepProps) {
  return (
    <>
      <header className={styles.homeHeader}>
        <h1>개떡찰떡</h1>
        <button aria-label="알림" type="button">
          <Bell size={20} aria-hidden="true" />
        </button>
      </header>

      <section className={styles.homeHero}>
        <div>
          <h2>
            개떡처럼 말해도,
            <br />
            찰떡같이 광고로.
          </h2>
          <p>레퍼런스를 고르거나, 사진을 올리거나, 그냥 대충 말해보세요.</p>
        </div>
        <div className={styles.homeMascot} aria-hidden="true">
          <span />
        </div>
      </section>

      <div className={styles.homeActionList}>
        <button type="button" onClick={onOpenReference}>
          <span className={styles.homeActionIcon} data-tone="lime">
            <Grid3X3 size={22} aria-hidden="true" />
          </span>
          <span>
            <strong>레퍼런스 보고 만들기</strong>
            <small>마음에 드는 광고 스타일을 골라보세요</small>
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>

        <button type="button">
          <span className={styles.homeActionIcon} data-tone="purple">
            <ImageIcon size={22} aria-hidden="true" />
          </span>
          <span>
            <strong>내 사진으로 만들기</strong>
            <small>상품 사진을 올리면 광고로 만들어드려요</small>
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>

        <button type="button" onClick={onOpenChat}>
          <span className={styles.homeActionIcon} data-tone="coral">
            <MessageCircle size={22} aria-hidden="true" />
          </span>
          <span>
            <strong>대화로 시작하기</strong>
            <small>대충 말해도 AI가 알아서 물어봐요</small>
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button data-active="true" type="button">
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button">
          <Briefcase size={18} aria-hidden="true" />
          보관함
        </button>
        <button type="button">
          <Package size={18} aria-hidden="true" />
          브랜드 키트
        </button>
        <button type="button">
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
