"use client";

import {
  Bell,
  Briefcase,
  ChevronRight,
  Home,
  Palette,
  Search,
  Settings,
  Sparkles,
  Store,
  User,
  Zap
} from "lucide-react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { archivedCreatives, brandFacts, myActivitySummary, myProfile } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

export function MyPageStep() {
  const router = useRouter();
  const activeAd = archivedCreatives.find((creative) => creative.status === "generating");

  return (
    <>
      <header className={styles.myHeader}>
        <h1>마이페이지</h1>
        <div>
          <button aria-label="알림" type="button" onClick={() => router.push(buildNotificationHref())}>
            <Bell size={19} aria-hidden="true" />
          </button>
          <button aria-label="설정" type="button" onClick={() => router.push(buildMyHref("settings"))}>
            <Settings size={19} aria-hidden="true" />
          </button>
        </div>
      </header>

      <button className={styles.myProfileCard} type="button" onClick={() => router.push(buildMyHref("account"))}>
        <span aria-hidden="true">
          <User size={30} />
        </span>
        <div>
          <strong>{myProfile.ownerName}</strong>
          <p>{myProfile.email}</p>
          <small>{myProfile.plan}</small>
        </div>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <button className={styles.myBrandBanner} type="button" onClick={() => router.push(buildBrandKitHref("complete"))}>
        <Store size={24} aria-hidden="true" />
        <strong>
          브랜드 키트 사용 중
          <small>
            {brandFacts.name} · {brandFacts.tone} · 크림/핑크톤
          </small>
        </strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <section className={styles.myStatsGrid} aria-label="활동 요약">
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{myActivitySummary.generatedAds}개</strong>
          <span>생성한 광고</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{myActivitySummary.savedAds}개</strong>
          <span>저장된 광고</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
          <strong>{myActivitySummary.activeJobs}개</strong>
          <span>생성 중 작업</span>
        </button>
        <button type="button" onClick={() => router.push(buildMyHref("usage"))}>
          <strong>{myActivitySummary.remainingCredits}회</strong>
          <span>남은 생성 횟수</span>
        </button>
      </section>

      {activeAd ? (
        <button className={styles.myProgressCard} type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
          <span data-tone={activeAd.tone} aria-hidden="true" />
          <strong>
            {activeAd.title}
            <small>{activeAd.subtitle}</small>
          </strong>
          <em>{activeAd.progress}%</em>
          <i aria-hidden="true">
            <b style={{ width: `${activeAd.progress}%` }} />
          </i>
          <small>진행 상황 보기</small>
        </button>
      ) : null}

      <section className={styles.myMenuList}>
        <div>
          <h2>메뉴</h2>
          <button type="button" onClick={() => router.push(buildMyHref("usage"))}>
            전체 보기
          </button>
        </div>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <Briefcase size={18} aria-hidden="true" />
          <strong>
            내 찰떡 광고
            <small>저장한 광고를 확인하고 관리해요</small>
          </strong>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
        <button type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
          <Palette size={18} aria-hidden="true" />
          <strong>
            브랜드 키트 관리
            <small>가게 정보와 브랜드 톤을 관리해요</small>
          </strong>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
      </section>

      <button className={styles.myFloatingCta} type="button" onClick={() => router.push(buildDashboardHref("studio"))}>
        <Zap size={18} aria-hidden="true" />
        광고 만들기
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
        <button data-active="true" type="button">
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
