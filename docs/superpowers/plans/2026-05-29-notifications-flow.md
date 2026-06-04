# Notifications Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mobile notification management flow from `images/개떡찰떡_앱 알림 관리.png`: notification center, completion detail, failure detail, and notification settings.

**Architecture:** Add a clean `/notifications` route family rather than query-string surfaces. Keep notification data mocked in `lib/mock-dashboard-data.ts`, route construction in `lib/notification-navigation.ts`, and the visual UI in focused `components/generate/*` components using the existing `MobileShell` and `generate.module.css` design system.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS Modules, lucide-react, Vitest, Playwright.

---

## Reference Analysis

The reference image contains four mobile screens:

1. **알림 센터**
   - Header: title `알림`, check icon, settings icon.
   - Filter tabs: `전체`, `생성 완료`, `생성 중`, `실패`, `브랜드`.
   - Notification cards:
     - Completion card with thumbnail, green dot, CTA `결과 확인하기`.
     - In-progress card with circular `68%` progress, CTA `진행 상황 보기`.
     - Failure card with red warning visual, CTA `다시 시도`.
     - Brand kit card with teal icon, CTA `브랜드 키트 보기`.
   - Pull hint copy: `위로 당기면 새로고침`.
   - Bottom tabs: `마이페이지` active.

2. **생성 완료 상세**
   - Back header: `알림 상세`.
   - Soft lime success hero with check icon.
   - Brief summary table: `광고 목적`, `상품 / 서비스`, `분위기`, `사용 채널`, `생성 수량`.
   - Completed creative preview row.
   - Primary CTA `결과 확인하기`.
   - Secondary CTAs `내 광고 보관함 보기`, `비슷한 스타일 더 보기`.
   - Success notice: generated ads were saved automatically.

3. **생성 실패 상세**
   - Back header: `알림 상세`.
   - Soft peach failure hero with warning icon.
   - Saved brief summary.
   - Primary CTA `다시 생성하기`.
   - Secondary CTAs `브리프 수정하기`, `내 광고 보관함 보기`.
   - Info notice: failed generation is not deducted from quota.

4. **알림 설정**
   - Back header: `알림 설정`.
   - Toggle groups:
     - `생성 완료 알림`, `생성 실패 알림`, `저장 완료 알림`, `브랜드 키트 알림`, `추천 레퍼런스 알림`, `프로모션 알림`.
     - `앱 내 알림`, `푸시 알림`, `이메일 알림`.
   - Primary CTA `설정 저장하기`.
   - Helper text: `언제든지 변경할 수 있어요.`
   - Bottom tabs: `마이페이지` active.

## File Structure

- Create: `apps/web/lib/notification-navigation.ts`
  - Builds clean notification URLs.
- Create: `apps/web/lib/notification-navigation.test.ts`
  - Verifies URL construction.
- Modify: `apps/web/lib/mock-dashboard-data.ts`
  - Adds mock notification items and notification settings data.
- Create: `apps/web/components/generate/NotificationCenterStep.tsx`
  - Renders notification list, filters, and bottom tabs.
- Create: `apps/web/components/generate/NotificationDetailStep.tsx`
  - Renders success/failure detail screens.
- Create: `apps/web/components/generate/NotificationSettingsStep.tsx`
  - Renders notification toggles and save action.
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
  - Wires the bell icon to notifications.
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
  - Wires the bell icon to notifications.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Passes notification navigation callbacks.
- Create: `apps/web/app/notifications/page.tsx`
- Create: `apps/web/app/notifications/complete/page.tsx`
- Create: `apps/web/app/notifications/failed/page.tsx`
- Create: `apps/web/app/notifications/settings/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`
  - Adds notification cards, status heroes, toggle rows, and progress ring styles.
- Modify: `apps/web/e2e/chat-start.spec.ts`
  - Adds smoke coverage for notification routes and key CTAs.
- Modify: `apps/web/README.md`
  - Adds new service screen addresses.

---

### Task 1: Notification Navigation Helper

**Files:**
- Create: `apps/web/lib/notification-navigation.ts`
- Create: `apps/web/lib/notification-navigation.test.ts`

- [ ] **Step 1: Write the failing navigation test**

```ts
import { describe, expect, it } from "vitest";
import { buildNotificationHref } from "./notification-navigation";

describe("notification navigation", () => {
  it("builds clean notification hrefs", () => {
    expect(buildNotificationHref()).toBe("/notifications");
    expect(buildNotificationHref("center")).toBe("/notifications");
    expect(buildNotificationHref("complete")).toBe("/notifications/complete");
    expect(buildNotificationHref("failed")).toBe("/notifications/failed");
    expect(buildNotificationHref("settings")).toBe("/notifications/settings");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/web
npm run test -- --run lib/notification-navigation.test.ts
```

Expected: FAIL because `notification-navigation.ts` does not exist.

- [ ] **Step 3: Add the helper**

```ts
export type NotificationStep = "center" | "complete" | "failed" | "settings";

export function buildNotificationHref(step: NotificationStep = "center"): string {
  if (step === "center") {
    return "/notifications";
  }

  return `/notifications/${step}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd apps/web
npm run test -- --run lib/notification-navigation.test.ts
```

Expected: PASS.

### Task 2: Mock Notification Data

**Files:**
- Modify: `apps/web/lib/mock-dashboard-data.ts`

- [ ] **Step 1: Add notification types and mock data**

Add exports near the existing mock data:

```ts
export type MockNotificationType = "complete" | "progress" | "failed" | "brand";

export type MockNotification = {
  id: string;
  type: MockNotificationType;
  title: string;
  subtitle: string;
  time: string;
  ctaLabel: string;
  target: "complete" | "generating" | "failed" | "brand-kit";
  progress?: number;
  creativeId?: string;
};

export const mockNotifications: MockNotification[] = [
  {
    id: "notice-complete",
    type: "complete",
    title: "찰떡 광고 시안이 완성됐어요",
    subtitle: "딸기라떼 신메뉴 광고",
    time: "방금 전",
    ctaLabel: "결과 확인하기",
    target: "complete",
    creativeId: "result-1"
  },
  {
    id: "notice-progress",
    type: "progress",
    title: "광고 생성 중이에요",
    subtitle: "카페 할인 이벤트",
    time: "2분 전",
    ctaLabel: "진행 상황 보기",
    target: "generating",
    progress: 68
  },
  {
    id: "notice-failed",
    type: "failed",
    title: "광고 생성에 실패했어요",
    subtitle: "리뷰 이벤트 포스터",
    time: "3분 전",
    ctaLabel: "다시 시도",
    target: "failed"
  },
  {
    id: "notice-brand",
    type: "brand",
    title: "브랜드 키트가 저장됐어요",
    subtitle: "도민 카페 정보가 다음 광고에 적용돼요.",
    time: "10분 전",
    ctaLabel: "브랜드 키트 보기",
    target: "brand-kit"
  }
];

export const notificationSettings = [
  { id: "generation-complete", label: "생성 완료 알림", description: "광고가 완성되면 알려드려요.", enabled: true },
  { id: "generation-failed", label: "생성 실패 알림", description: "생성 실패 시 원인과 대안을 알려드려요.", enabled: true },
  { id: "save-complete", label: "저장 완료 알림", description: "광고를 저장하면 알려드려요.", enabled: true },
  { id: "brand-kit", label: "브랜드 키트 알림", description: "브랜드 키트 변경/저장 시 알려드려요.", enabled: true },
  { id: "reference", label: "추천 레퍼런스 알림", description: "새로운 스타일을 추천해드려요.", enabled: false },
  { id: "promotion", label: "프로모션 알림", description: "이벤트 및 혜택 정보를 알려드려요.", enabled: false }
];

export const notificationChannels = [
  { id: "in-app", label: "앱 내 알림", enabled: true },
  { id: "push", label: "푸시 알림", enabled: true },
  { id: "email", label: "이메일 알림", enabled: false }
];
```

- [ ] **Step 2: Run type check through build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build still passes.

### Task 3: Notification Center Screen

**Files:**
- Create: `apps/web/components/generate/NotificationCenterStep.tsx`
- Create: `apps/web/app/notifications/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create route shell**

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { NotificationCenterStep } from "@/components/generate/NotificationCenterStep";

export default function NotificationsPage() {
  return (
    <MobileShell>
      <NotificationCenterStep />
    </MobileShell>
  );
}
```

- [ ] **Step 2: Implement the notification center component**

Use these interactions:

```tsx
"use client";

import { Bell, Briefcase, CheckCircle2, Home, Search, Settings, Sparkles, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildAdHref } from "@/lib/ad-navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { mockNotifications } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

const filters = ["전체", "생성 완료", "생성 중", "실패", "브랜드"];

export function NotificationCenterStep() {
  const router = useRouter();

  function openNotification(target: string, creativeId?: string) {
    if (target === "complete") router.push(buildNotificationHref("complete"));
    if (target === "generating") router.push(buildDashboardHref("chat", "generating"));
    if (target === "failed") router.push(buildNotificationHref("failed"));
    if (target === "brand-kit") router.push(buildBrandKitHref("complete"));
    if (target === "ad" && creativeId) router.push(buildAdHref(creativeId));
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
            <div className={styles.notificationThumb} data-type={item.type}>
              {item.progress ? <strong>{item.progress}%</strong> : <Bell size={24} aria-hidden="true" />}
            </div>
            <div>
              <h2>{item.title}</h2>
              <p>{item.subtitle}</p>
              <small>{item.time}</small>
            </div>
            <button type="button" onClick={() => openNotification(item.target, item.creativeId)}>
              {item.ctaLabel}
            </button>
          </article>
        ))}
      </section>

      <p className={styles.pullHint}>위로 당기면 새로고침</p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}><Home size={18} aria-hidden="true" />홈</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}><Search size={18} aria-hidden="true" />레퍼런스</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("studio"))}><Sparkles size={18} aria-hidden="true" />스튜디오</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}><Briefcase size={18} aria-hidden="true" />보관함</button>
        <button data-active="true" type="button" onClick={() => router.push(buildDashboardHref("brand"))}><User size={18} aria-hidden="true" />마이페이지</button>
      </nav>
    </>
  );
}
```

- [ ] **Step 3: Add focused CSS**

Add styles for:

```css
.notificationHeader {}
.notificationFilterRow {}
.notificationList {}
.notificationCard {}
.notificationCard[data-type="complete"] {}
.notificationCard[data-type="progress"] {}
.notificationCard[data-type="failed"] {}
.notificationCard[data-type="brand"] {}
.notificationThumb {}
.notificationUnread {}
.pullHint {}
```

Expected visual match: list spacing, pill filters, soft green/purple/red/teal status accents, one CTA per card.

### Task 4: Notification Detail Screens

**Files:**
- Create: `apps/web/components/generate/NotificationDetailStep.tsx`
- Create: `apps/web/app/notifications/complete/page.tsx`
- Create: `apps/web/app/notifications/failed/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create route pages**

`complete/page.tsx`:

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { NotificationDetailStep } from "@/components/generate/NotificationDetailStep";

export default function CompleteNotificationPage() {
  return (
    <MobileShell>
      <NotificationDetailStep variant="complete" />
    </MobileShell>
  );
}
```

`failed/page.tsx`:

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { NotificationDetailStep } from "@/components/generate/NotificationDetailStep";

export default function FailedNotificationPage() {
  return (
    <MobileShell>
      <NotificationDetailStep variant="failed" />
    </MobileShell>
  );
}
```

- [ ] **Step 2: Implement shared detail component**

Required CTAs:

```tsx
"use client";

import { ArrowLeft, ArrowRight, Check, Info, RotateCcw, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildAdHref } from "@/lib/ad-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

type NotificationDetailStepProps = {
  variant: "complete" | "failed";
};

export function NotificationDetailStep({ variant }: NotificationDetailStepProps) {
  const router = useRouter();
  const isComplete = variant === "complete";

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildNotificationHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>알림 상세</h1>
        <span />
      </header>

      <section className={styles.notificationDetailHero} data-variant={variant}>
        <span>{isComplete ? <Check size={34} aria-hidden="true" /> : <TriangleAlert size={34} aria-hidden="true" />}</span>
        <h2>{isComplete ? "광고 시안이 완성됐어요!" : "광고 생성에 실패했어요"}</h2>
        <p>{isComplete ? "딸기라떼 신메뉴 광고" : "일시적인 문제로 광고 시안을 만들지 못했어요."}</p>
      </section>

      <section className={styles.notificationBriefCard}>
        <h2>{isComplete ? "광고 브리프" : "저장된 브리프"}</h2>
        <dl>
          <div><dt>광고 목적</dt><dd>신메뉴 출시</dd></div>
          <div><dt>상품 / 서비스</dt><dd>딸기라떼</dd></div>
          <div><dt>분위기</dt><dd>감성적인 카페 무드</dd></div>
          <div><dt>사용 채널</dt><dd>인스타 피드 1:1</dd></div>
          {isComplete ? <div><dt>생성 수량</dt><dd>4개 시안</dd></div> : <div><dt>이미지 방향</dt><dd>크림톤 배경, 중앙 상품 배치</dd></div>}
        </dl>
      </section>

      {isComplete ? <div className={styles.notificationPreviewStrip} aria-label="완성된 시안 미리보기"><span /><span /><span /><span /></div> : null}

      <button className={styles.primaryButton} type="button" onClick={() => router.push(isComplete ? buildAdHref("result-1") : buildDashboardHref("chat", "generating"))}>
        {isComplete ? "결과 확인하기" : "다시 생성하기"} <ArrowRight size={18} aria-hidden="true" />
      </button>

      <div className={styles.notificationActionRow}>
        <button type="button" onClick={() => router.push(isComplete ? buildDashboardHref("ads") : buildDashboardHref("chat"))}>
          {isComplete ? "내 광고 보관함 보기" : "브리프 수정하기"}
        </button>
        <button type="button" onClick={() => router.push(isComplete ? buildDashboardHref("reference") : buildDashboardHref("ads"))}>
          {isComplete ? "비슷한 스타일 더 보기" : "내 광고 보관함 보기"}
        </button>
      </div>

      <p className={styles.notificationInfoBox}>
        <Info size={16} aria-hidden="true" />
        {isComplete ? "생성된 광고는 내 광고 보관함에 자동 저장됐어요." : "실패한 생성은 생성 횟수에서 차감되지 않아요."}
      </p>
    </>
  );
}
```

### Task 5: Notification Settings Screen

**Files:**
- Create: `apps/web/components/generate/NotificationSettingsStep.tsx`
- Create: `apps/web/app/notifications/settings/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create settings route page**

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { NotificationSettingsStep } from "@/components/generate/NotificationSettingsStep";

export default function NotificationSettingsPage() {
  return (
    <MobileShell>
      <NotificationSettingsStep />
    </MobileShell>
  );
}
```

- [ ] **Step 2: Implement toggles with local state**

Use `notificationSettings` and `notificationChannels`. Toggles must be real buttons with `aria-pressed`.

```tsx
"use client";

import { ArrowLeft, Bell, Briefcase, Home, Image, Mail, Search, Sparkles, User } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import { notificationChannels, notificationSettings } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

export function NotificationSettingsStep() {
  const router = useRouter();
  const [settings, setSettings] = useState(notificationSettings);
  const [channels, setChannels] = useState(notificationChannels);

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildNotificationHref())}>
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
            onClick={() => setSettings((current) => current.map((setting) => setting.id === item.id ? { ...setting, enabled: !setting.enabled } : setting))}
          >
            <span><Bell size={18} aria-hidden="true" /></span>
            <strong>{item.label}<small>{item.description}</small></strong>
            <i />
          </button>
        ))}
      </section>

      <section className={styles.notificationSettingsGroup}>
        <h2>알림 방식</h2>
        {channels.map((item) => (
          <button
            aria-pressed={item.enabled}
            className={styles.notificationToggleRow}
            key={item.id}
            type="button"
            onClick={() => setChannels((current) => current.map((channel) => channel.id === item.id ? { ...channel, enabled: !channel.enabled } : channel))}
          >
            <span>{item.id === "email" ? <Mail size={18} aria-hidden="true" /> : <Image size={18} aria-hidden="true" />}</span>
            <strong>{item.label}</strong>
            <i />
          </button>
        ))}
      </section>

      <button className={styles.primaryButton} type="button" onClick={() => router.push(buildNotificationHref())}>
        설정 저장하기
      </button>
      <p className={styles.settingsHint}>언제든지 변경할 수 있어요.</p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}><Home size={18} aria-hidden="true" />홈</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}><Search size={18} aria-hidden="true" />레퍼런스</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("studio"))}><Sparkles size={18} aria-hidden="true" />스튜디오</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}><Briefcase size={18} aria-hidden="true" />보관함</button>
        <button data-active="true" type="button" onClick={() => router.push(buildDashboardHref("brand"))}><User size={18} aria-hidden="true" />마이페이지</button>
      </nav>
    </>
  );
}
```

### Task 6: Wire Existing Bell Icons

**Files:**
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`

- [ ] **Step 1: Add callback props**

In `HomeStartStepProps` and `RecentAdsStepProps`, add:

```ts
onOpenNotifications: () => void;
```

- [ ] **Step 2: Wire bell buttons**

Change bell buttons to:

```tsx
<button aria-label="알림" type="button" onClick={onOpenNotifications}>
```

- [ ] **Step 3: Pass router navigation from client**

In `ChatGenerateClient.tsx`, import:

```ts
import { buildNotificationHref } from "@/lib/notification-navigation";
```

Pass:

```tsx
onOpenNotifications={() => router.push(buildNotificationHref())}
```

Expected: tapping the bell on home or ads opens `/notifications`.

### Task 7: E2E and Docs

**Files:**
- Modify: `apps/web/e2e/chat-start.spec.ts`
- Modify: `apps/web/README.md`

- [ ] **Step 1: Add E2E coverage**

```ts
test("notification flow opens details and settings", async ({ page }) => {
  await page.goto("/notifications");
  await expect(page.getByRole("heading", { name: "알림" })).toBeVisible();

  await page.getByRole("button", { name: "결과 확인하기" }).click();
  await expect(page).toHaveURL(/\/notifications\/complete$/);
  await expect(page.getByRole("heading", { name: "광고 시안이 완성됐어요!" })).toBeVisible();

  await page.goto("/notifications");
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page).toHaveURL(/\/notifications\/failed$/);
  await expect(page.getByRole("heading", { name: "광고 생성에 실패했어요" })).toBeVisible();

  await page.goto("/notifications");
  await page.getByRole("button", { name: "알림 설정" }).click();
  await expect(page).toHaveURL(/\/notifications\/settings$/);
  await expect(page.getByRole("heading", { name: "알림 설정" })).toBeVisible();
});
```

- [ ] **Step 2: Add README routes**

Add to service addresses:

```text
http://localhost:3000/notifications
http://localhost:3000/notifications/complete
http://localhost:3000/notifications/failed
http://localhost:3000/notifications/settings
```

### Task 8: Verification

**Files:**
- No edits.

- [ ] **Step 1: Run focused tests**

```bash
cd apps/web
npm run test -- --run lib/notification-navigation.test.ts app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run lint**

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 3: Run production build**

```bash
cd apps/web
npm run build
```

Expected: PASS and routes include `/notifications`, `/notifications/complete`, `/notifications/failed`, `/notifications/settings`.

- [ ] **Step 4: Run E2E**

```bash
cd apps/web
npm run e2e
```

Expected: PASS.

- [ ] **Step 5: Capture mobile screenshots**

```bash
cd apps/web
node - <<'NODE'
const { chromium } = require('@playwright/test');
const routes = [
  ['center', '/notifications'],
  ['complete', '/notifications/complete'],
  ['failed', '/notifications/failed'],
  ['settings', '/notifications/settings'],
];
(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const [name, route] of routes) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true });
    await page.goto(`http://127.0.0.1:3000${route}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `/tmp/easyads-notifications-${name}.png`, fullPage: true });
    await page.close();
  }
  await browser.close();
})();
NODE
```

Expected screenshots:

```text
/tmp/easyads-notifications-center.png
/tmp/easyads-notifications-complete.png
/tmp/easyads-notifications-failed.png
/tmp/easyads-notifications-settings.png
```

## Self-Review

- Spec coverage: all four reference screens are represented by route pages and components.
- Navigation coverage: bell icon entry, detail CTAs, settings entry, bottom tabs are included.
- UI/UX coverage: touch targets are button-based, each screen has one primary CTA, icon-only buttons use `aria-label`, deep links are clean.
- Testing coverage: navigation unit test, client callback tests, route E2E, lint/build, and mobile screenshots are covered.
