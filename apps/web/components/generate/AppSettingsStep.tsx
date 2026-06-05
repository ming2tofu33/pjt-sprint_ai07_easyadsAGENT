"use client";

import {
  ArrowLeft,
  Bell,
  Briefcase,
  ChevronRight,
  FileText,
  HelpCircle,
  Home,
  Image,
  LogOut,
  Mail,
  MessageCircle,
  Search,
  Shield,
  SlidersHorizontal,
  Sparkles,
  User
} from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { appSettings } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import { goBackOrPush } from "@/lib/navigation-history";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { buildOnboardingHref } from "@/lib/onboarding-navigation";
import styles from "./generate.module.css";

function iconForSetting(id: string) {
  if (id === "save-format" || id === "image-quality") {
    return Image;
  }
  if (id === "default-channel") {
    return SlidersHorizontal;
  }
  return Bell;
}

export function AppSettingsStep() {
  const router = useRouter();

  function handleSettingClick(id: string) {
    if (id === "notifications") {
      router.push(buildNotificationHref("settings"));
    }
  }

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => goBackOrPush(router, buildMyHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>설정</h1>
        <span />
      </header>

      <section className={styles.settingsListGroup}>
        <h2>앱 설정</h2>
        {appSettings.map((item) => {
          const Icon = iconForSetting(item.id);
          return (
            <button key={item.id} type="button" onClick={() => handleSettingClick(item.id)}>
              <Icon size={18} aria-hidden="true" />
              <strong>{item.label}</strong>
              <span>{item.value}</span>
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          );
        })}
      </section>

      <section className={styles.settingsListGroup}>
        <h2>도움말</h2>
        <button type="button" onClick={() => router.push(buildOnboardingHref())}>
          <HelpCircle size={18} aria-hidden="true" />
          <strong>사용법 다시 보기</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <button type="button">
          <MessageCircle size={18} aria-hidden="true" />
          <strong>자주 묻는 질문</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <button type="button">
          <Mail size={18} aria-hidden="true" />
          <strong>문의하기</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </section>

      <section className={styles.settingsListGroup}>
        <h2>기타</h2>
        <button type="button">
          <Shield size={18} aria-hidden="true" />
          <strong>개인정보 처리방침</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <button type="button">
          <FileText size={18} aria-hidden="true" />
          <strong>이용약관</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <button data-danger="true" type="button">
          <LogOut size={18} aria-hidden="true" />
          <strong>로그아웃</strong>
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </section>

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
        <button data-active="true" type="button" onClick={() => router.push(buildDashboardHref("my"))}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
