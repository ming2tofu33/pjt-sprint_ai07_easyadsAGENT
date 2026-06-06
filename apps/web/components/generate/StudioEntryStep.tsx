"use client";

import { ChevronLeft, Home, Image as ImageIcon, Lightbulb, MessageCircle, Search, Sparkles, Upload, User } from "lucide-react";
import styles from "./generate.module.css";

type StudioEntryStepProps = {
  onGoHome: () => void;
  onOpenChat: () => void;
  onOpenPhoto: () => void;
  onOpenReference: () => void;
  onOpenRecentAds: () => void;
  onOpenBrandKit: () => void;
};

export function StudioEntryStep({
  onGoHome,
  onOpenChat,
  onOpenPhoto,
  onOpenReference,
  onOpenRecentAds,
  onOpenBrandKit
}: StudioEntryStepProps) {
  return (
    <>
      <header className={styles.studioTopNav}>
        <button aria-label="홈으로" type="button" onClick={onGoHome}>
          <ChevronLeft size={22} aria-hidden="true" />
        </button>
        <h1>광고 만들기</h1>
        <span />
      </header>

      <section className={styles.studioIntro}>
        <h2>어떻게 시작할까요?</h2>
        <p>원하는 방식을 선택하면 AI가 도와드릴게요.</p>
      </section>

      <div className={styles.studioOptionList}>
        <button className={styles.studioOptionCard} type="button" onClick={onOpenReference}>
          <span className={styles.optionThumb} data-kind="reference">
            <ImageIcon size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>샘플 보고 만들기</strong>
            <p>마음에 드는 광고 스타일을 골라 내 광고로 바꿔요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>

        <button className={styles.studioOptionCard} type="button" onClick={onOpenPhoto}>
          <span className={styles.optionThumb} data-kind="photo">
            <Upload size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>내 사진으로 만들기</strong>
            <p>상품 사진이나 매장 사진을 올리면 AI가 광고 방향을 제안해요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>

        <button className={styles.studioOptionCard} type="button" onClick={onOpenChat}>
          <span className={styles.optionThumb} data-kind="chat">
            <MessageCircle size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>대화로 시작하기</strong>
            <p>이미지 없어도 괜찮아요. 대충 말해도 AI가 질문하며 브리프를 완성해요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>
      </div>

      <p className={styles.studioTip}>
        <Lightbulb size={17} aria-hidden="true" />
        <span>어떤 방식이든 AI가 광고 브리프를 만들고 찰떡같은 광고 이미지를 제안해드려요.</span>
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
        <button data-active="true" type="button">
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button type="button" onClick={onOpenRecentAds}>
          <ImageIcon size={18} aria-hidden="true" />
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
