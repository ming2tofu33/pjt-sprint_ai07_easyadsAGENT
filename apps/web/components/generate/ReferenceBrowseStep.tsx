"use client";

import { Bookmark, Home, Search, Sparkles } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import styles from "./generate.module.css";

type ReferenceBrowseStepProps = {
  state: ChatFlowState;
  progress: number;
  onShowProgress: () => void;
};

const categories = ["전체", "카페", "음식점", "뷰티", "포스터", "스토리"];

const references = [
  { title: "감성 카페 신메뉴 포스터", tone: "pink" },
  { title: "브런치 카페 이벤트 배너", tone: "mint" },
  { title: "카페 할인 프로모션", tone: "cream" },
  { title: "봄 시즌 감성 광고", tone: "coral" }
];

export function ReferenceBrowseStep({ state, progress, onShowProgress }: ReferenceBrowseStepProps) {
  const brief = buildBrief(state);
  const safeProgress = Math.max(12, Math.min(progress, 99));

  return (
    <>
      <div className={styles.progressBanner}>
        <span className={styles.spinnerDot} />
        <strong>{brief.item} 광고 생성 중 · {safeProgress}%</strong>
        <span>약 {Math.max(5, Math.ceil((100 - safeProgress) / 4))}초 남음</span>
        <button type="button" onClick={onShowProgress}>
          진행 상황 보기
        </button>
      </div>

      <header className={styles.referenceHeader}>
        <div>
          <p>레퍼런스</p>
          <h1>찰떡 레퍼런스 둘러보기</h1>
        </div>
        <Search size={22} aria-hidden="true" />
      </header>

      <label className={styles.searchField}>
        <Search size={17} aria-hidden="true" />
        <input aria-label="레퍼런스 검색어" placeholder="검색어를 입력하세요" />
      </label>

      <div className={styles.categoryScroller} aria-label="레퍼런스 카테고리">
        {categories.map((category) => (
          <button className={category === "전체" ? styles.categoryActive : undefined} key={category} type="button">
            {category}
          </button>
        ))}
      </div>

      <section className={styles.referenceGrid} aria-label="광고 레퍼런스 목록">
        {references.map((item, index) => (
          <article className={`${styles.referenceCard} ${styles[`referenceTone${item.tone}`]}`} key={item.title}>
            <button aria-label={`${item.title} 저장`} type="button">
              <Bookmark size={15} aria-hidden="true" />
            </button>
            <div className={styles.mockCup}>
              <span />
            </div>
            <h2>{item.title}</h2>
            <p>{index % 2 === 0 ? brief.copy : "부드러운 색감과 여백이 살아있는 광고 스타일"}</p>
          </article>
        ))}
      </section>

      <p className={styles.browseNote}>
        <Sparkles size={17} aria-hidden="true" />
        광고가 완성되면 알려드릴게요. 기다리는 동안 다른 스타일을 둘러볼 수 있어요.
      </p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <span data-active="true">
          <Home size={18} aria-hidden="true" />
          홈
        </span>
        <span>
          <Search size={18} aria-hidden="true" />
          레퍼런스
        </span>
        <span>
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </span>
        <span>
          <Bookmark size={18} aria-hidden="true" />
          보관함
        </span>
      </nav>
    </>
  );
}
