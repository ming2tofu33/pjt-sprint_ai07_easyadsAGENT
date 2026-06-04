"use client";

import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { ArrowLeft, Briefcase, ChevronDown, ChevronRight, Home, Info, Search, Sparkles, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { readGeneratedCreatives } from "@/lib/generated-creative-storage";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import { goBackOrPush } from "@/lib/navigation-history";
import styles from "./generate.module.css";

const usagePeriods = [
  {
    id: "this-month",
    label: "이번 달",
    description: "이번 달에 완성된 이미지 결과를 기준으로 봅니다."
  },
  {
    id: "last-month",
    label: "지난 달",
    description: "기간별 사용량 데이터가 연결되면 지난 달 내역을 보여드려요."
  },
  {
    id: "last-3-months",
    label: "최근 3개월",
    description: "여러 달의 사용 흐름은 사용량 데이터가 연결되면 표시됩니다."
  }
];

export function UsageSummaryStep() {
  const router = useRouter();
  const [sessionCreatives, setSessionCreatives] = useState<MockCreative[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState(usagePeriods[0]);
  const [isPeriodMenuOpen, setIsPeriodMenuOpen] = useState(false);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [showUsageDetails, setShowUsageDetails] = useState(false);
  const visibleHistory = showAllHistory ? sessionCreatives : sessionCreatives.slice(0, 3);
  const hasMoreHistory = sessionCreatives.length > visibleHistory.length;

  useEffect(() => {
    setSessionCreatives(readGeneratedCreatives());
  }, []);

  return (
    <>
      <header className={`${styles.stepHeader} ${styles.usageHeader}`}>
        <button aria-label="뒤로" type="button" onClick={() => goBackOrPush(router, buildMyHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>이미지 생성 내역</h1>
        <button
          aria-expanded={isPeriodMenuOpen}
          aria-label="기간 선택"
          className={styles.myPeriodButton}
          type="button"
          onClick={() => setIsPeriodMenuOpen((current) => !current)}
        >
          {selectedPeriod.label} <ChevronDown size={15} aria-hidden="true" />
        </button>
      </header>

      {isPeriodMenuOpen ? (
        <section className={styles.usagePeriodMenu} aria-label="사용량 기간 선택">
          {usagePeriods.map((period) => (
            <button
              data-active={selectedPeriod.id === period.id ? "true" : undefined}
              key={period.id}
              type="button"
              onClick={() => {
                setSelectedPeriod(period);
                setIsPeriodMenuOpen(false);
              }}
            >
              <strong>{period.label}</strong>
              <small>{period.description}</small>
            </button>
          ))}
        </section>
      ) : null}

      <section className={styles.usageHeroCard}>
        <div className={styles.usageRing} style={{ "--progress": "0%" } as CSSProperties}>
          <strong>
            {sessionCreatives.length}
            <small>/ 생성</small>
          </strong>
          <span>결과</span>
        </div>
        <div>
          <p>{selectedPeriod.label}에 생성한 결과</p>
          <strong>{sessionCreatives.length}개</strong>
          <small>
            월간 사용량과 결제 한도는 사용량 데이터가 연동되면 표시됩니다.
          </small>
        </div>
        <i aria-hidden="true">
          <b style={{ width: "0%" }} />
        </i>
      </section>

      <p className={styles.usageNotice}>
        <Info size={16} aria-hidden="true" />
        실제 완성된 이미지 결과만 사용 내역에 표시됩니다.
      </p>

      <section className={styles.usageHistoryList}>
        <div>
          <h2>최근 사용 내역</h2>
          <button
            aria-expanded={showAllHistory}
            type="button"
            onClick={() => setShowAllHistory((current) => !current)}
          >
            {showAllHistory ? "최근만 보기" : "전체 보기"}
          </button>
        </div>
        {sessionCreatives.length > 0 ? (
          <>
            {visibleHistory.map((item) => (
              <article key={item.id}>
                <span data-tone={item.tone} aria-hidden="true" />
                <strong>
                  {item.title}
                  <small>생성일 · {item.savedAt ?? item.date}</small>
                </strong>
                <em>1회</em>
              </article>
            ))}
            {hasMoreHistory ? (
              <p className={styles.usageInlineNote}>나머지 {sessionCreatives.length - visibleHistory.length}개 내역은 전체 보기에서 확인할 수 있어요.</p>
            ) : null}
          </>
        ) : (
          <section className={styles.emptyResultPanel} aria-label="사용 내역 없음">
            <Sparkles size={24} aria-hidden="true" />
            <strong>아직 생성된 이미지 결과가 없어요</strong>
            <p>이미지를 생성하면 여기에 차곡차곡 표시돼요.</p>
          </section>
        )}
      </section>

      <button
        aria-expanded={showUsageDetails}
        className={styles.secondaryButton}
        type="button"
        onClick={() => setShowUsageDetails((current) => !current)}
      >
        {showUsageDetails ? "사용량 안내 닫기" : "사용량 더 보기"} <ChevronRight size={17} aria-hidden="true" />
      </button>

      {showUsageDetails ? (
        <section className={styles.usageDetailsPanel} aria-label="사용량 상세 안내">
          <h2>사용량 안내</h2>
          <ul>
            <li>실제 완성된 이미지 결과만 사용 내역에 표시됩니다.</li>
            <li>이미지 생성에 실패한 요청은 사용 내역에 포함하지 않습니다.</li>
            <li>월간 사용량과 결제 한도는 결제 정보가 연결되면 함께 표시됩니다.</li>
          </ul>
        </section>
      ) : null}

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}>
          <Search size={18} aria-hidden="true" />
          레퍼런스
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("studio"))}>
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <Briefcase size={18} aria-hidden="true" />
          보관함
        </button>
        <button data-active="true" type="button" onClick={() => router.push(buildMyHref())}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
