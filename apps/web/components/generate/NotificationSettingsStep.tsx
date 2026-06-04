"use client";

import {
  ArrowLeft,
  Bell,
  Briefcase,
  Home,
  Mail,
  MonitorSmartphone,
  Search,
  Sparkles,
  User,
  Vibrate
} from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { notificationChannels, notificationSettings } from "@/lib/mock-dashboard-data";
import { goBackOrPush } from "@/lib/navigation-history";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

const channelIconById = {
  "in-app": MonitorSmartphone,
  push: Vibrate,
  email: Mail
};

export function NotificationSettingsStep() {
  const router = useRouter();
  const [settings, setSettings] = useState(notificationSettings);
  const [channels, setChannels] = useState(notificationChannels);

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => goBackOrPush(router, buildNotificationHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>알림 설정</h1>
        <span />
      </header>

      <section className={styles.notificationSettingsGroup}>
        <h2>알림 종류</h2>
        {settings.map((item) => (
          <button
            aria-pressed={item.enabled}
            className={styles.notificationToggleRow}
            key={item.id}
            type="button"
            onClick={() =>
              setSettings((current) =>
                current.map((setting) => (setting.id === item.id ? { ...setting, enabled: !setting.enabled } : setting))
              )
            }
          >
            <span>
              <Bell size={18} aria-hidden="true" />
            </span>
            <strong>
              {item.label}
              <small>{item.description}</small>
            </strong>
            <i />
          </button>
        ))}
      </section>

      <section className={styles.notificationSettingsGroup}>
        <h2>알림 방식</h2>
        {channels.map((item) => {
          const Icon = channelIconById[item.id as keyof typeof channelIconById];
          return (
            <button
              aria-pressed={item.enabled}
              className={styles.notificationToggleRow}
              key={item.id}
              type="button"
              onClick={() =>
                setChannels((current) =>
                  current.map((channel) => (channel.id === item.id ? { ...channel, enabled: !channel.enabled } : channel))
                )
              }
            >
              <span>
                <Icon size={18} aria-hidden="true" />
              </span>
              <strong>{item.label}</strong>
              <i />
            </button>
          );
        })}
      </section>

      <button className={styles.primaryButton} type="button" onClick={() => router.push(buildNotificationHref())}>
        설정 저장하기
      </button>
      <p className={styles.settingsHint}>언제든지 변경할 수 있어요.</p>

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
