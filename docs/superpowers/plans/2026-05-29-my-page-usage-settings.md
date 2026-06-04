# My Page Usage Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mobile My Page, account/store information, usage summary, and app settings screens from `images/개떡찰떡_앱설정 및 사용량 관리 화면.png`.

**Architecture:** Add clean service routes for the account area: `/my`, `/my/account`, `/my/usage`, and `/settings`. Keep the current `/brand` page as a compatibility alias during this mock stage, but route all bottom-tab and profile actions to `/my`. Use focused React client components under `components/generate`, mock data in `lib/mock-dashboard-data.ts`, and URL helpers in `lib/my-navigation.ts`.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS Modules, lucide-react, Vitest, Playwright.

---

## Reference Analysis

The reference image has four related mobile screens:

1. **마이페이지 홈**
   - Header: `마이페이지`, notification icon, settings icon.
   - Profile block: avatar, name `도민 사장님`, email, plan badge.
   - Brand kit banner: active kit summary with store icon.
   - Activity summary grid:
     - `생성한 광고 12개`
     - `저장된 광고 8개`
     - `생성 중 작업 1개`
     - `남은 생성 횟수 5회`
   - In-progress ad card: thumbnail, title, progress bar `68%`, CTA `진행 상황 보기`.
   - Menu list:
     - `내 찰떡 광고`
     - `브랜드 키트 관리`
   - Floating CTA: `+ 광고 만들기`.
   - Bottom tab: `마이페이지` active.

2. **계정 및 가게 정보**
   - Back header: `계정 및 가게 정보`.
   - Account info card:
     - name, email, login method.
   - Store info card:
     - store name, business type, region, SNS.
   - Connected brand kit card.
   - CTAs:
     - `계정 정보 수정`
     - `브랜드 키트 수정`
   - Bottom tab: `마이페이지` active.

3. **생성 사용량**
   - Back header: `생성 사용량`, period dropdown `이번 달`.
   - Usage card:
     - circular usage ring `12/20 사용`.
     - remaining count `8회`.
     - usage bar `60%`.
   - Notice: generation consumes 1 credit, failed generations are not deducted.
   - Recent usage history list with thumbnail, title, created date, usage count.
   - CTA: `사용량 더 보기`.
   - Bottom tab: `마이페이지` active.

4. **설정**
   - Back header: `설정`.
   - App settings list:
     - notification settings, completion/failure notification state.
     - default save format `PNG`.
     - default channel `인스타 피드 1:1`.
     - default image quality `고화질`.
     - push notification permission `ON`.
   - Help list:
     - usage guide, FAQ, contact.
   - Legal/other list:
     - privacy policy, terms, logout.
   - Bottom tab: `마이페이지` active.

## URL Decision

Use clean production-like URLs:

```text
/my
/my/account
/my/usage
/settings
```

Keep `/brand` for now as a compatibility route that renders the new My Page or redirects later. Existing `/brand/kit/*` remains the brand kit setup flow.

## File Structure

- Create: `apps/web/lib/my-navigation.ts`
  - Builds clean My Page URLs.
- Create: `apps/web/lib/my-navigation.test.ts`
  - Verifies route construction.
- Modify: `apps/web/lib/dashboard-navigation.ts`
  - Add `my` surface and map legacy `brand` to `/my`.
- Modify: `apps/web/lib/mock-dashboard-data.ts`
  - Add account, usage, usage history, and settings mock data.
- Create: `apps/web/components/generate/MyPageStep.tsx`
  - Renders the My Page home screen.
- Create: `apps/web/components/generate/AccountInfoStep.tsx`
  - Renders account/store info screen.
- Create: `apps/web/components/generate/UsageSummaryStep.tsx`
  - Renders usage screen.
- Create: `apps/web/components/generate/AppSettingsStep.tsx`
  - Renders settings screen.
- Create: `apps/web/app/my/page.tsx`
- Create: `apps/web/app/my/account/page.tsx`
- Create: `apps/web/app/my/usage/page.tsx`
- Create: `apps/web/app/settings/page.tsx`
- Modify: `apps/web/app/brand/page.tsx`
  - Keep compatibility by rendering My Page.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Replace brand surface usage with my surface where appropriate.
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
- Modify: `apps/web/components/generate/StudioEntryStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/NotificationCenterStep.tsx`
- Modify: `apps/web/components/generate/NotificationSettingsStep.tsx`
  - Bottom-tab and profile actions should open `/my`.
- Modify: `apps/web/components/generate/generate.module.css`
  - Add My Page, account, usage ring, settings list, and floating CTA styles.
- Modify: `apps/web/README.md`
  - Add new addresses.
- Modify: `apps/web/e2e/chat-start.spec.ts`
  - Add flow coverage.
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Add callback and render coverage.

---

### Task 1: Navigation Helper

**Files:**
- Create: `apps/web/lib/my-navigation.ts`
- Create: `apps/web/lib/my-navigation.test.ts`
- Modify: `apps/web/lib/dashboard-navigation.ts`

- [ ] **Step 1: Write navigation tests**

Create `apps/web/lib/my-navigation.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildMyHref } from "./my-navigation";

describe("my navigation", () => {
  it("builds clean my page hrefs", () => {
    expect(buildMyHref()).toBe("/my");
    expect(buildMyHref("home")).toBe("/my");
    expect(buildMyHref("account")).toBe("/my/account");
    expect(buildMyHref("usage")).toBe("/my/usage");
    expect(buildMyHref("settings")).toBe("/settings");
  });
});
```

- [ ] **Step 2: Add helper implementation**

Create `apps/web/lib/my-navigation.ts`:

```ts
export type MyPageStep = "home" | "account" | "usage" | "settings";

export function buildMyHref(step: MyPageStep = "home"): string {
  if (step === "home") {
    return "/my";
  }

  if (step === "settings") {
    return "/settings";
  }

  return `/my/${step}`;
}
```

- [ ] **Step 3: Update dashboard navigation**

In `apps/web/lib/dashboard-navigation.ts`, change:

```ts
export const dashboardSurfaces = ["home", "studio", "reference", "ads", "brand", "chat", "photo"] as const;
```

to:

```ts
export const dashboardSurfaces = ["home", "studio", "reference", "ads", "my", "brand", "chat", "photo"] as const;
```

Update `buildDashboardHref` so `my` and legacy `brand` both resolve to the new My Page:

```ts
if (surface === "my" || surface === "brand") {
  return "/my";
}
```

Place this before the generic `return \`/${surface}\`;`.

- [ ] **Step 4: Run navigation tests**

Run:

```bash
cd apps/web
npm run test -- --run lib/my-navigation.test.ts lib/dashboard-navigation.test.ts
```

Expected: PASS after updating existing dashboard expectations from `/brand` to `/my` where needed.

### Task 2: Mock Data

**Files:**
- Modify: `apps/web/lib/mock-dashboard-data.ts`

- [ ] **Step 1: Add My Page mock data**

Add after `brandFacts`:

```ts
export const myProfile = {
  ownerName: "도민 사장님",
  email: "domincafe@naver.com",
  plan: "무료 플랜 사용 중",
  loginMethod: "이메일 로그인"
};

export const myActivitySummary = {
  generatedAds: 12,
  savedAds: 8,
  activeJobs: 1,
  remainingCredits: 5,
  monthlyLimit: 20,
  usedCredits: 12,
  usagePercent: 60
};

export const usageHistory = [
  {
    id: "usage-strawberry",
    title: "딸기라떼 신메뉴 광고",
    createdAt: "2024.05.29 14:32",
    count: "1회 사용",
    tone: "strawberry" as CreativeTone
  },
  {
    id: "usage-cafe-sale",
    title: "카페 할인 이벤트",
    createdAt: "2024.05.28 11:10",
    count: "1회 사용",
    tone: "mint" as CreativeTone
  },
  {
    id: "usage-summer",
    title: "여름 시즌 포스터",
    createdAt: "2024.05.27 16:45",
    count: "1회 사용",
    tone: "sunny" as CreativeTone
  }
];

export const appSettings = [
  { id: "notifications", label: "알림 설정", value: "ON" },
  { id: "complete-alert", label: "생성 완료 알림", value: "ON" },
  { id: "promo-alert", label: "프로모션 알림", value: "OFF" },
  { id: "save-format", label: "기본 저장 형식", value: "PNG" },
  { id: "default-channel", label: "기본 사용 채널", value: "인스타 피드 1:1" },
  { id: "image-quality", label: "기본 이미지 품질", value: "고화질" },
  { id: "push-permission", label: "푸시 알림 허용", value: "ON" }
];
```

### Task 3: My Page Home

**Files:**
- Create: `apps/web/components/generate/MyPageStep.tsx`
- Create: `apps/web/app/my/page.tsx`
- Modify: `apps/web/app/brand/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create route page**

`apps/web/app/my/page.tsx`:

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { MyPageStep } from "@/components/generate/MyPageStep";

export default function MyPage() {
  return (
    <MobileShell>
      <MyPageStep />
    </MobileShell>
  );
}
```

- [ ] **Step 2: Keep `/brand` compatibility**

Replace `apps/web/app/brand/page.tsx` with:

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { MyPageStep } from "@/components/generate/MyPageStep";

export default function BrandPage() {
  return (
    <MobileShell>
      <MyPageStep />
    </MobileShell>
  );
}
```

- [ ] **Step 3: Implement My Page component**

`MyPageStep` should render:

```tsx
"use client";

import { Bell, Briefcase, ChevronRight, Home, Palette, Search, Settings, Sparkles, User, Zap } from "lucide-react";
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
          <button aria-label="알림" type="button" onClick={() => router.push(buildNotificationHref())}><Bell size={19} aria-hidden="true" /></button>
          <button aria-label="설정" type="button" onClick={() => router.push(buildMyHref("settings"))}><Settings size={19} aria-hidden="true" /></button>
        </div>
      </header>

      <section className={styles.myProfileCard}>
        <span aria-hidden="true" />
        <div>
          <strong>{myProfile.ownerName}</strong>
          <p>{myProfile.email}</p>
          <small>{myProfile.plan}</small>
        </div>
      </section>

      <button className={styles.myBrandBanner} type="button" onClick={() => router.push(buildBrandKitHref("complete"))}>
        <Palette size={22} aria-hidden="true" />
        <strong>브랜드 키트 사용 중<small>{brandFacts.name} · {brandFacts.tone} · 크림/핑크톤</small></strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <section className={styles.myStatsGrid} aria-label="활동 요약">
        <article><strong>{myActivitySummary.generatedAds}개</strong><span>생성한 광고</span></article>
        <article><strong>{myActivitySummary.savedAds}개</strong><span>저장된 광고</span></article>
        <article><strong>{myActivitySummary.activeJobs}개</strong><span>생성 중 작업</span></article>
        <article><strong>{myActivitySummary.remainingCredits}회</strong><span>남은 생성 횟수</span></article>
      </section>

      {activeAd ? (
        <button className={styles.myProgressCard} type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
          <span data-tone={activeAd.tone} />
          <strong>{activeAd.title}<small>{activeAd.progress}%</small></strong>
          <i><b style={{ width: `${activeAd.progress}%` }} /></i>
        </button>
      ) : null}

      <section className={styles.myMenuList}>
        <h2>메뉴</h2>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}><Briefcase size={18} aria-hidden="true" />내 찰떡 광고<ChevronRight size={17} aria-hidden="true" /></button>
        <button type="button" onClick={() => router.push(buildBrandKitHref("info"))}><Palette size={18} aria-hidden="true" />브랜드 키트 관리<ChevronRight size={17} aria-hidden="true" /></button>
      </section>

      <button className={styles.myFloatingCta} type="button" onClick={() => router.push(buildDashboardHref("studio"))}><Zap size={18} aria-hidden="true" />광고 만들기</button>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}><Home size={18} aria-hidden="true" />홈</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}><Search size={18} aria-hidden="true" />레퍼런스</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("studio"))}><Sparkles size={18} aria-hidden="true" />스튜디오</button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}><Briefcase size={18} aria-hidden="true" />보관함</button>
        <button data-active="true" type="button"><User size={18} aria-hidden="true" />마이페이지</button>
      </nav>
    </>
  );
}
```

### Task 4: Account / Store Info

**Files:**
- Create: `apps/web/components/generate/AccountInfoStep.tsx`
- Create: `apps/web/app/my/account/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create page and component**

The page wraps `AccountInfoStep` in `MobileShell`.

The component should include:

```tsx
"use client";

import { ArrowLeft, ChevronRight, Mail, MapPin, Store, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { brandFacts, myProfile } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import styles from "./generate.module.css";

export function AccountInfoStep() {
  const router = useRouter();

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildMyHref())}><ArrowLeft size={20} aria-hidden="true" /></button>
        <h1>계정 및 가게 정보</h1>
        <span />
      </header>

      <section className={styles.myInfoCard}>
        <h2>계정 정보</h2>
        <dl>
          <div><dt><User size={17} aria-hidden="true" />이름</dt><dd>{myProfile.ownerName}</dd></div>
          <div><dt><Mail size={17} aria-hidden="true" />이메일</dt><dd>{myProfile.email}</dd></div>
          <div><dt>로그인 방식</dt><dd>{myProfile.loginMethod}</dd></div>
        </dl>
      </section>

      <section className={styles.myInfoCard}>
        <h2>가게 정보</h2>
        <dl>
          <div><dt><Store size={17} aria-hidden="true" />가게 이름</dt><dd>{brandFacts.name}</dd></div>
          <div><dt>업종</dt><dd>{brandFacts.businessType} / 디저트</dd></div>
          <div><dt><MapPin size={17} aria-hidden="true" />지역 / 상권</dt><dd>서울 마포구 연남동</dd></div>
          <div><dt>SNS 계정</dt><dd>{brandFacts.sns}</dd></div>
        </dl>
      </section>

      <button className={styles.myLinkedBrandCard} type="button" onClick={() => router.push(buildBrandKitHref("complete"))}>
        <Store size={24} aria-hidden="true" />
        <strong>{brandFacts.name}<small>{brandFacts.tone} · 대표 상품: {brandFacts.products}</small></strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <button className={styles.secondaryButton} type="button">계정 정보 수정</button>
      <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>브랜드 키트 수정</button>
    </>
  );
}
```

### Task 5: Usage Summary

**Files:**
- Create: `apps/web/components/generate/UsageSummaryStep.tsx`
- Create: `apps/web/app/my/usage/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create usage page**

The page wraps `UsageSummaryStep` in `MobileShell`.

- [ ] **Step 2: Implement usage component**

Required content:

```tsx
"use client";

import { ArrowLeft, ChevronDown, ChevronRight, Info } from "lucide-react";
import { useRouter } from "next/navigation";
import { myActivitySummary, usageHistory } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import styles from "./generate.module.css";

export function UsageSummaryStep() {
  const router = useRouter();

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildMyHref())}><ArrowLeft size={20} aria-hidden="true" /></button>
        <h1>생성 사용량</h1>
        <button aria-label="기간 선택" type="button">이번 달 <ChevronDown size={15} aria-hidden="true" /></button>
      </header>

      <section className={styles.usageHeroCard}>
        <div className={styles.usageRing} style={{ "--progress": `${myActivitySummary.usagePercent}%` } as React.CSSProperties}>
          <strong>{myActivitySummary.usedCredits}<small>/ {myActivitySummary.monthlyLimit}</small></strong>
          <span>사용</span>
        </div>
        <div>
          <p>남은 생성 횟수</p>
          <strong>{myActivitySummary.remainingCredits + 3}회</strong>
          <small>이번 달 총 {myActivitySummary.monthlyLimit}회 중 {myActivitySummary.usedCredits}회를 사용했어요.</small>
        </div>
        <i><b style={{ width: `${myActivitySummary.usagePercent}%` }} /></i>
      </section>

      <p className={styles.usageNotice}><Info size={16} aria-hidden="true" />광고 시안 1회 생성 시 생성 횟수 1회가 차감돼요. 실패한 생성은 차감되지 않아요.</p>

      <section className={styles.usageHistoryList}>
        <h2>최근 사용 내역</h2>
        {usageHistory.map((item) => (
          <article key={item.id}>
            <span data-tone={item.tone} />
            <strong>{item.title}<small>생성일 · {item.createdAt}</small></strong>
            <em>{item.count}</em>
          </article>
        ))}
      </section>

      <button className={styles.secondaryButton} type="button">사용량 더 보기 <ChevronRight size={17} aria-hidden="true" /></button>
    </>
  );
}
```

Implementation note: import `type CSSProperties` rather than using `React.CSSProperties` directly.

### Task 6: App Settings

**Files:**
- Create: `apps/web/components/generate/AppSettingsStep.tsx`
- Create: `apps/web/app/settings/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Create settings page**

The page wraps `AppSettingsStep` in `MobileShell`.

- [ ] **Step 2: Implement settings component**

The settings screen should use grouped rows:

```tsx
"use client";

import { ArrowLeft, Bell, ChevronRight, FileText, HelpCircle, Image, LogOut, Mail, MessageCircle, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { appSettings } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

export function AppSettingsStep() {
  const router = useRouter();

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildMyHref())}><ArrowLeft size={20} aria-hidden="true" /></button>
        <h1>설정</h1>
        <span />
      </header>

      <section className={styles.settingsListGroup}>
        <h2>앱 설정</h2>
        {appSettings.map((item) => (
          <button key={item.id} type="button" onClick={() => item.id === "notifications" ? router.push(buildNotificationHref("settings")) : undefined}>
            <Bell size={18} aria-hidden="true" />
            <strong>{item.label}</strong>
            <span>{item.value}</span>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        ))}
      </section>

      <section className={styles.settingsListGroup}>
        <h2>도움말</h2>
        <button type="button"><HelpCircle size={18} aria-hidden="true" /><strong>개떡찰떡 사용법</strong><ChevronRight size={16} aria-hidden="true" /></button>
        <button type="button"><MessageCircle size={18} aria-hidden="true" /><strong>자주 묻는 질문</strong><ChevronRight size={16} aria-hidden="true" /></button>
        <button type="button"><Mail size={18} aria-hidden="true" /><strong>문의하기</strong><ChevronRight size={16} aria-hidden="true" /></button>
      </section>

      <section className={styles.settingsListGroup}>
        <h2>기타</h2>
        <button type="button"><Shield size={18} aria-hidden="true" /><strong>개인정보 처리방침</strong><ChevronRight size={16} aria-hidden="true" /></button>
        <button type="button"><FileText size={18} aria-hidden="true" /><strong>이용약관</strong><ChevronRight size={16} aria-hidden="true" /></button>
        <button data-danger="true" type="button"><LogOut size={18} aria-hidden="true" /><strong>로그아웃</strong><ChevronRight size={16} aria-hidden="true" /></button>
      </section>
    </>
  );
}
```

### Task 7: Wire Navigation Across Existing Screens

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
- Modify: `apps/web/components/generate/StudioEntryStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/NotificationCenterStep.tsx`
- Modify: `apps/web/components/generate/NotificationSettingsStep.tsx`

- [ ] **Step 1: Rename intent, keep prop compatibility if needed**

Prefer `onOpenMyPage` for new components. Existing `onOpenBrandKit` can remain temporarily, but should route to `/my`.

- [ ] **Step 2: Route profile, My Page bottom tab, and notification settings bottom tab to `/my`**

In `ChatGenerateClient.tsx`, pass:

```tsx
onOpenBrandKit={() => navigateTo("my")}
```

Every bottom tab labeled `마이페이지` should call:

```ts
router.push(buildDashboardHref("my"))
```

or receive a callback that does the same.

### Task 8: Tests and Docs

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
- Modify: `apps/web/e2e/chat-start.spec.ts`
- Modify: `apps/web/README.md`

- [ ] **Step 1: Add unit coverage**

Add assertions:

```ts
fireEvent.click(screen.getByRole("button", { name: /마이페이지/ }));
expect(navigationMock.push).toHaveBeenCalledWith("/my");
```

Add direct render coverage for `initialSurface="my"` if `DashboardSurface` supports it.

- [ ] **Step 2: Add E2E coverage**

```ts
test("my page account usage and settings are directly addressable", async ({ page }) => {
  await page.goto("/my");
  await expect(page.getByRole("heading", { name: "마이페이지" })).toBeVisible();

  await page.goto("/my/account");
  await expect(page.getByRole("heading", { name: "계정 및 가게 정보" })).toBeVisible();

  await page.goto("/my/usage");
  await expect(page.getByRole("heading", { name: "생성 사용량" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "설정" })).toBeVisible();
});
```

- [ ] **Step 3: Add README routes**

```text
http://localhost:3000/my
http://localhost:3000/my/account
http://localhost:3000/my/usage
http://localhost:3000/settings
```

### Task 9: Verification

**Files:**
- No edits.

- [ ] **Step 1: Run focused unit tests**

```bash
cd apps/web
npm run test -- --run lib/my-navigation.test.ts lib/dashboard-navigation.test.ts app/generate/chat/ChatGenerateClient.test.tsx
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

Expected: PASS and route list includes `/my`, `/my/account`, `/my/usage`, `/settings`.

- [ ] **Step 4: Run E2E**

```bash
cd apps/web
npm run e2e
```

Expected: PASS.

- [ ] **Step 5: Capture mobile screenshots**

With the dev server running:

```bash
cd apps/web
node - <<'NODE'
const { chromium } = require('@playwright/test');
const routes = [
  ['home', '/my'],
  ['account', '/my/account'],
  ['usage', '/my/usage'],
  ['settings', '/settings'],
];
(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const [name, route] of routes) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true });
    await page.goto(`http://127.0.0.1:3000${route}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `/tmp/easyads-my-${name}.png`, fullPage: true });
    await page.close();
  }
  await browser.close();
})();
NODE
```

Expected screenshots:

```text
/tmp/easyads-my-home.png
/tmp/easyads-my-account.png
/tmp/easyads-my-usage.png
/tmp/easyads-my-settings.png
```

## Self-Review

- Spec coverage: all four reference screens are represented.
- URL coverage: clean service URLs are defined, with `/brand` kept as compatibility.
- UX coverage: one primary action per screen, bottom tabs keep `마이페이지` active, icon-only buttons have labels, and settings rows remain tappable at 44px+.
- Testing coverage: helper tests, client navigation tests, E2E route tests, lint/build, and screenshots are included.
