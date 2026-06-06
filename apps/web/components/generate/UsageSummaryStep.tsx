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
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

const usagePeriods = [
  {
    id: "this-month",
    label: "이번 달",
    description: "이번 달 생성 사용량을 확인하는 기준 기간입니다."
  },
  {
    id: "last-month",
    label: "지난 달",
    description: "사용량 데이터가 연결되면 지난 달 집계를 보여드려요."
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
        <h1>생성 사용량</h1>
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
          <strong>연결 전</strong>
          <span>사용량</span>
        </div>
        <div>
          <p>{selectedPeriod.label} 생성 사용량</p>
          <strong>사용량 정보 연결 전</strong>
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
        아래 완성 이미지 내역은 참고용이며, 실제 월간 사용량과 결제 한도는 사용량 데이터가 연결되면 표시됩니다.
      </p>

      <section className={styles.usageHistoryList}>
        <div>
          <h2>이번에 생성한 결과</h2>
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
          <section className={styles.emptyResultPanel} aria-label="생성 결과 내역 없음">
            <MascotImage role="usageWaiting" decorative className={styles.usageEmptyMascot} />
            <strong>아직 생성된 이미지 결과가 없어요</strong>
            <p>이미지를 생성하면 완성된 결과가 여기에 차곡차곡 표시돼요.</p>
          </section>
        )}
      </section>

      <button
        aria-expanded={showUsageDetails}
        className={`${styles.secondaryButton} ${styles.usageDetailsButton}`}
        type="button"
        onClick={() => setShowUsageDetails((current) => !current)}
      >
        {showUsageDetails ? "사용량 안내 닫기" : "사용량 더 보기"} <ChevronRight size={17} aria-hidden="true" />
      </button>

      {showUsageDetails ? (
        <section className={styles.usageDetailsPanel} aria-label="사용량 상세 안내">
          <h2>사용량 안내</h2>
          <ul>
            <li>월간 사용량과 결제 한도는 사용량 데이터가 연결되면 표시됩니다.</li>
            <li>이미지 생성에 실패한 요청은 사용량 집계에 포함하지 않는 기준으로 정리할 예정입니다.</li>
            <li>완성 이미지 내역은 참고용이며 실제 사용량 집계와는 분리됩니다.</li>
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
          찾기
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
