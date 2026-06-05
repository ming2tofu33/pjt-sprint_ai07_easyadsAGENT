"use client";

import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
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
import { MascotImage } from "./MascotImage";
import styles from "./generate.module.css";

const filters = ["전체", "생성 완료", "생성 중", "실패", "브랜드"];

const iconByType: Record<MockNotificationType, typeof Bell> = {
  complete: ImageIcon,
  progress: Sparkles,
  failed: CircleAlert,
  brand: Store
};

const filterTypeByLabel: Record<string, MockNotificationType | "all"> = {
  전체: "all",
  "생성 완료": "complete",
  "생성 중": "progress",
  실패: "failed",
  브랜드: "brand"
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
  const [showSampleNotifications, setShowSampleNotifications] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState("전체");
  const [hasReadAll, setHasReadAll] = useState(false);
  const filteredNotifications = useMemo(() => {
    const selectedType = filterTypeByLabel[selectedFilter] ?? "all";
    if (selectedType === "all") {
      return mockNotifications;
    }
    return mockNotifications.filter((item) => item.type === selectedType);
  }, [selectedFilter]);

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
          <button aria-label="모두 읽음" type="button" onClick={() => setHasReadAll(true)}>
            <CheckCircle2 size={19} aria-hidden="true" />
          </button>
          <button aria-label="알림 설정" type="button" onClick={() => router.push(buildNotificationHref("settings"))}>
            <Settings size={19} aria-hidden="true" />
          </button>
        </div>
      </header>

      <div className={styles.sampleLibraryHeader}>
        <h2 className={styles.archiveSectionTitle}>알림 목록</h2>
        <button type="button" onClick={() => setShowSampleNotifications((current) => !current)}>
          {showSampleNotifications ? "숨기기" : "보기"}
        </button>
      </div>

      {showSampleNotifications ? (
        <>
          <p className={styles.sampleNotice}>
            아래 항목은 실제 푸시/생성 이벤트가 아니라 화면 확인용 샘플 알림입니다.
          </p>

          <div className={styles.notificationFilterRow} aria-label="알림 필터">
            {filters.map((filter) => (
              <button
                className={filter === selectedFilter ? styles.categoryActive : undefined}
                key={filter}
                type="button"
                onClick={() => setSelectedFilter(filter)}
              >
                {filter}
              </button>
            ))}
          </div>

          {filteredNotifications.length > 0 ? (
            <section className={styles.notificationList} aria-label="샘플 알림 목록">
              {filteredNotifications.map((item) => (
                <article className={styles.notificationCard} data-type={item.type} key={item.id}>
                  {hasReadAll ? null : <span className={styles.notificationUnread} aria-hidden="true" />}
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
          ) : (
            <section className={styles.emptyResultPanel} aria-label="필터 결과 없음">
              <MascotImage role="notificationLetter" decorative className={styles.emptyMascot} />
              <strong>조건에 맞는 알림이 없어요</strong>
              <p>다른 알림 종류를 선택해보세요.</p>
            </section>
          )}
        </>
      ) : (
        <section className={styles.emptyResultPanel} aria-label="실제 알림 없음">
          <MascotImage role="notificationBell" decorative className={styles.emptyMascot} />
          <strong>아직 연결된 실제 알림이 없어요</strong>
          <p>생성 완료, 실패, 브랜드 키트 이벤트가 연결되면 이곳에 표시됩니다.</p>
          <button className={styles.secondaryButton} type="button" onClick={() => setShowSampleNotifications(true)}>
            샘플 알림 보기
          </button>
        </section>
      )}

      <p className={styles.pullHint}>위로 당기면 새로고침</p>

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
