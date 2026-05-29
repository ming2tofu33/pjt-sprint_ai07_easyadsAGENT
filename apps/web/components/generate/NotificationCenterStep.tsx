"use client";

import type { CSSProperties } from "react";
import {
  Bell,
  Briefcase,
  CheckCircle2,
  CircleAlert,
  Home,
  Image as ImageIcon,
  Search,
  Settings,
  Sparkles,
  Store,
  User
} from "lucide-react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { mockNotifications, type MockNotification, type MockNotificationType } from "@/lib/mock-dashboard-data";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

const filters = ["전체", "생성 완료", "생성 중", "실패", "브랜드"];

const iconByType: Record<MockNotificationType, typeof Bell> = {
  complete: ImageIcon,
  progress: Sparkles,
  failed: CircleAlert,
  brand: Store
};

function NotificationThumb({ item }: { item: MockNotification }) {
  const Icon = iconByType[item.type];

  if (item.progress) {
    return (
      <div className={styles.notificationProgressRing} style={{ "--progress": `${item.progress}%` } as CSSProperties}>
        <strong>{item.progress}%</strong>
      </div>
    );
  }

  return (
    <span className={styles.notificationThumb} data-type={item.type}>
      <Icon size={24} aria-hidden="true" />
    </span>
  );
}

export function NotificationCenterStep() {
  const router = useRouter();

  function openNotification(item: MockNotification) {
    if (item.target === "complete") {
      router.push(buildNotificationHref("complete"));
      return;
    }

    if (item.target === "generating") {
      router.push(buildDashboardHref("chat", "generating"));
      return;
    }

    if (item.target === "failed") {
      router.push(buildNotificationHref("failed"));
      return;
    }

    router.push(buildBrandKitHref("complete"));
  }

  return (
    <>
      <header className={styles.notificationHeader}>
        <h1>알림</h1>
        <div>
          <button aria-label="모두 읽음" type="button">
            <CheckCircle2 size={19} aria-hidden="true" />
          </button>
          <button aria-label="알림 설정" type="button" onClick={() => router.push(buildNotificationHref("settings"))}>
            <Settings size={19} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={styles.notificationFilterRow} aria-label="알림 필터">
        {filters.map((filter) => (
          <button className={filter === "전체" ? styles.categoryActive : undefined} key={filter} type="button">
            {filter}
          </button>
        ))}
      </div>

      <section className={styles.notificationList} aria-label="알림 목록">
        {mockNotifications.map((item) => (
          <article className={styles.notificationCard} data-type={item.type} key={item.id}>
            <span className={styles.notificationUnread} aria-hidden="true" />
            <NotificationThumb item={item} />
            <div>
              <h2>{item.title}</h2>
              <p>{item.subtitle}</p>
              <small>{item.time}</small>
            </div>
            <button type="button" onClick={() => openNotification(item)}>
              {item.ctaLabel}
            </button>
          </article>
        ))}
      </section>

      <p className={styles.pullHint}>위로 당기면 새로고침</p>

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
        <button data-active="true" type="button" onClick={() => router.push(buildDashboardHref("my"))}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
