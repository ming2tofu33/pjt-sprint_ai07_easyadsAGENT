"use client";

import type { CSSProperties } from "react";
import { ArrowLeft, Briefcase, ChevronDown, ChevronRight, Home, Info, Search, Sparkles, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { myActivitySummary, usageHistory } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import styles from "./generate.module.css";

export function UsageSummaryStep() {
  const router = useRouter();

  return (
    <>
      <header className={`${styles.stepHeader} ${styles.usageHeader}`}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildMyHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>생성 사용량</h1>
        <button aria-label="기간 선택" className={styles.myPeriodButton} type="button">
          이번 달 <ChevronDown size={15} aria-hidden="true" />
        </button>
      </header>

      <section className={styles.usageHeroCard}>
        <div className={styles.usageRing} style={{ "--progress": `${myActivitySummary.usagePercent}%` } as CSSProperties}>
          <strong>
            {myActivitySummary.usedCredits}
            <small>/ {myActivitySummary.monthlyLimit}</small>
          </strong>
          <span>사용</span>
        </div>
        <div>
          <p>남은 생성 횟수</p>
          <strong>{myActivitySummary.monthlyLimit - myActivitySummary.usedCredits}회</strong>
          <small>
            이번 달 총 {myActivitySummary.monthlyLimit}회 중 {myActivitySummary.usedCredits}회를 사용했어요.
          </small>
        </div>
        <i aria-hidden="true">
          <b style={{ width: `${myActivitySummary.usagePercent}%` }} />
        </i>
      </section>

      <p className={styles.usageNotice}>
        <Info size={16} aria-hidden="true" />
        광고 시안 1회 생성 시 생성 횟수 1회가 차감돼요. 실패한 생성은 차감되지 않아요.
      </p>

      <section className={styles.usageHistoryList}>
        <div>
          <h2>최근 사용 내역</h2>
          <button type="button">전체 보기</button>
        </div>
        {usageHistory.map((item) => (
          <article key={item.id}>
            <span data-tone={item.tone} aria-hidden="true" />
            <strong>
              {item.title}
              <small>생성일 · {item.createdAt}</small>
            </strong>
            <em>{item.count}</em>
          </article>
        ))}
      </section>

      <button className={styles.secondaryButton} type="button">
        사용량 더 보기 <ChevronRight size={17} aria-hidden="true" />
      </button>

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
