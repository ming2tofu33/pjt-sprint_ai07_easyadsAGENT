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
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { brandKitMeta, brandKitTone, readSavedBrandKit, type StoredBrandKit } from "@/lib/brand-kit-storage";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { myProfile } from "@/lib/mock-dashboard-data";
import { readGeneratedCreatives } from "@/lib/generated-creative-storage";
import { buildMyHref } from "@/lib/my-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

export function MyPageStep() {
  const router = useRouter();
  const [sessionCreativeCount, setSessionCreativeCount] = useState(0);
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);

  useEffect(() => {
    setSessionCreativeCount(readGeneratedCreatives().length);
    setBrandKit(readSavedBrandKit());
  }, []);

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

      <button className={styles.myBrandBanner} type="button" onClick={() => router.push(buildBrandKitHref(brandKit ? "complete" : "info"))}>
        <Store size={24} aria-hidden="true" />
        <strong>
          {brandKit ? "브랜드 키트 사용 중" : "브랜드 키트 연결 전"}
          <small>{brandKit ? `${brandKit.businessName} · ${brandKitTone(brandKit)} · ${brandKitMeta(brandKit)}` : "현재는 입력 흐름만 확인할 수 있어요"}</small>
        </strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <section className={styles.myStatsGrid} aria-label="활동 요약">
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{sessionCreativeCount}개</strong>
          <span>이번 세션 결과</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{sessionCreativeCount}개</strong>
          <span>저장 가능 결과</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
          <strong>0개</strong>
          <span>생성 중 작업</span>
        </button>
        <button type="button" onClick={() => router.push(buildMyHref("usage"))}>
          <strong>연결 전</strong>
          <span>남은 생성 횟수</span>
        </button>
      </section>

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
