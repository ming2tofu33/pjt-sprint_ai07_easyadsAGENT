"use client";

import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { ArrowLeft, Briefcase, ChevronDown, ChevronRight, Home, Info, Search, Sparkles, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { readGeneratedCreatives } from "@/lib/generated-creative-storage";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import styles from "./generate.module.css";

export function UsageSummaryStep() {
  const router = useRouter();
  const [sessionCreatives, setSessionCreatives] = useState<MockCreative[]>([]);

  useEffect(() => {
    setSessionCreatives(readGeneratedCreatives());
  }, []);

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
        <div className={styles.usageRing} style={{ "--progress": "0%" } as CSSProperties}>
          <strong>
            {sessionCreatives.length}
            <small>/ 세션</small>
          </strong>
          <span>결과</span>
        </div>
        <div>
          <p>이번 세션 실제 생성 결과</p>
          <strong>{sessionCreatives.length}개</strong>
          <small>
            월간 사용량과 결제 한도는 사용량 API가 연결되면 표시됩니다.
          </small>
        </div>
        <i aria-hidden="true">
          <b style={{ width: "0%" }} />
        </i>
      </section>

      <p className={styles.usageNotice}>
        <Info size={16} aria-hidden="true" />
        실제 이미지가 있는 결과만 이번 세션 사용 내역에 표시됩니다.
      </p>

      <section className={styles.usageHistoryList}>
        <div>
          <h2>최근 사용 내역</h2>
          <button type="button">전체 보기</button>
        </div>
        {sessionCreatives.length > 0 ? (
          sessionCreatives.map((item) => (
            <article key={item.id}>
              <span data-tone={item.tone} aria-hidden="true" />
              <strong>
                {item.title}
                <small>생성일 · {item.savedAt ?? item.date}</small>
              </strong>
              <em>1회</em>
            </article>
          ))
        ) : (
          <section className={styles.emptyResultPanel} aria-label="사용 내역 없음">
            <Sparkles size={24} aria-hidden="true" />
            <strong>아직 실제 생성 사용 내역이 없어요</strong>
            <p>이미지가 생성되면 이번 세션 내역에 표시됩니다.</p>
          </section>
        )}
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
