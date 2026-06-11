"use client";

import {
  Bell,
  Briefcase,
  ChevronRight,
  Home,
  LogIn,
  Palette,
  Search,
  Shield,
  Settings,
  Sparkles,
  Store,
  User,
  Zap
} from "lucide-react";
import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { brandKitFromServerResponse, brandKitMeta, brandKitTone, readSavedBrandKit, type StoredBrandKit } from "@/lib/brand-kit-storage";
import { buildLoginHref } from "@/lib/auth-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { getCurrentBrandKit, listArchiveItems } from "@/lib/api-client";
import { readGeneratedCreatives } from "@/lib/generated-creative-storage";
import { buildMyHref } from "@/lib/my-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { getCurrentAppUserAccess } from "@/lib/user-auth-client";
import type { AppUserProfile } from "@/lib/user-profile";
import styles from "./generate.module.css";

export function MyPageStep() {
  const router = useRouter();
  const [sessionCreativeCount, setSessionCreativeCount] = useState(0);
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);
  const [userProfile, setUserProfile] = useState<AppUserProfile | null>(null);
  const [canSeeAdminMode, setCanSeeAdminMode] = useState(false);
  const [savedArchiveCount, setSavedArchiveCount] = useState<number | null>(null);
  const [isArchiveCountLoading, setIsArchiveCountLoading] = useState(false);

  useEffect(() => {
    setSessionCreativeCount(readGeneratedCreatives().length);
    setBrandKit(readSavedBrandKit());
    void getCurrentAppUserAccess().then((access) => {
      setUserProfile(access.profile);
      setCanSeeAdminMode(access.isAdmin);
      if (!access.profile) {
        setSavedArchiveCount(null);
        setIsArchiveCountLoading(false);
        return;
      }

      // Server brand kit is the source of truth for signed-in users; local
      // storage is only a fallback for offline/unsynced devices.
      void getCurrentBrandKit({ userId: access.profile.id })
        .then((payload) => {
          const serverBrandKit = brandKitFromServerResponse(payload);
          if (serverBrandKit) {
            setBrandKit(serverBrandKit);
          }
        })
        .catch(() => {
          // Keep the local fallback already set above.
        });

      setIsArchiveCountLoading(true);
      void listArchiveItems({ limit: 1 })
        .then((response) => {
          setSavedArchiveCount(response.pagination.total);
        })
        .catch(() => {
          setSavedArchiveCount(null);
        })
        .finally(() => {
          setIsArchiveCountLoading(false);
        });
    });
  }, []);

  const profileCardHref = userProfile ? buildMyHref("account") : buildLoginHref(buildMyHref("account"));

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

      <button className={styles.myProfileCard} type="button" onClick={() => router.push(profileCardHref)}>
        <span className={userProfile?.avatarUrl ? styles.myProfileAvatar : undefined} aria-hidden="true">
          {userProfile?.avatarUrl ? <Image src={userProfile.avatarUrl} alt="" width={72} height={72} unoptimized /> : userProfile ? <User size={30} /> : <LogIn size={30} />}
        </span>
        <div>
          <strong>{userProfile ? userProfile.displayName : "로그인하고 내 광고 관리하기"}</strong>
          <p>{userProfile ? userProfile.email : "Google 계정으로 결과를 이어서 확인해요"}</p>
          <small>{userProfile ? userProfile.loginMethod : "로그인 필요"}</small>
        </div>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <button className={styles.myBrandBanner} type="button" onClick={() => router.push(buildBrandKitHref(brandKit ? "complete" : "start"))}>
        <Store size={24} aria-hidden="true" />
        <strong>
          {brandKit ? "브랜드 파일 사용 중" : "브랜드 파일 연결 전"}
          <small>{brandKit ? `${brandKit.businessName} · ${brandKitTone(brandKit)} · ${brandKitMeta(brandKit)}` : "가게 정보를 등록하면 광고 요청에 함께 반영돼요"}</small>
        </strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <section className={styles.myStatsGrid} aria-label="활동 요약">
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{userProfile ? `${sessionCreativeCount}개` : "로그인 전"}</strong>
          <span>{userProfile ? "이번 기기에서 만든 결과" : "생성 내역"}</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <strong>{userProfile ? (isArchiveCountLoading ? "확인 중" : savedArchiveCount !== null ? `${savedArchiveCount}개` : "연결 필요") : "로그인 전"}</strong>
          <span>저장한 결과</span>
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
          <strong>0개</strong>
          <span>생성 중 작업</span>
        </button>
        <button type="button" onClick={() => router.push(buildMyHref("usage"))}>
          <strong>연동 전</strong>
          <span>사용량 정보</span>
        </button>
      </section>

      <section className={styles.myMenuList}>
        <div>
          <h2>메뉴</h2>
        </div>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <Briefcase size={18} aria-hidden="true" />
          <strong>
            내 찰떡 광고
            <small>저장한 광고를 확인하고 관리해요</small>
          </strong>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
        <button type="button" onClick={() => router.push(buildBrandKitHref("start"))}>
          <Palette size={18} aria-hidden="true" />
          <strong>
            브랜드 파일 관리
            <small>가게 정보와 브랜드 톤을 관리해요</small>
          </strong>
          <ChevronRight size={17} aria-hidden="true" />
        </button>
        {canSeeAdminMode ? (
          <button type="button" onClick={() => router.push("/admin")}>
            <Shield size={18} aria-hidden="true" />
            <strong>
              운영자 모드
              <small>샘플과 운영 설정을 관리해요</small>
            </strong>
            <ChevronRight size={17} aria-hidden="true" />
          </button>
        ) : null}
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
        <button data-active="true" type="button">
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
