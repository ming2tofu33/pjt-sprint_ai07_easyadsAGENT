# Dashboard UI/UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the `/generate/chat` mobile dashboard mock closer to the reference images by improving navigation URLs, visual fidelity, accessibility, interaction feedback, and reusable UI structure.

**Architecture:** Keep the existing Next.js App Router page at `/generate/chat`, but move top-level app screen state into query-string backed navigation so home, studio, reference, ads, brand kit, and chat surfaces are directly addressable. Extract repeated dashboard data and visual card pieces into small files, then use the existing generate components to render richer mock screens without introducing backend dependencies.

**Tech Stack:** Next.js 14 App Router, React 18 client components, CSS Modules, Lucide React, Vitest, Testing Library, Playwright.

---

## Scope

This plan addresses the UI/UX gaps identified from the current implementation review:

- Cards still look like wireframe placeholders instead of advertising app surfaces.
- Dashboard surfaces are controlled only by React state, so direct addresses and browser back/forward are not reliable.
- Some interactive elements are below 44px touch target size.
- Emoji are used as structural UI symbols in production-facing UI text.
- Click actions such as save, edit, regenerate, and view status need visible feedback.
- Colors, radius, borders, focus states, and spacing need stronger token consistency.
- Key mock screens need documented direct URLs for review.

Out of scope:

- Real image generation.
- Real authentication, persistence, or database-backed saved ads.
- Replacing the current BFF/orchestrator API contracts.

## Address / URL Design

The app will continue to live under one route:

```text
http://localhost:3000/generate/chat
```

Top-level mock surfaces use a `surface` query parameter:

```text
http://localhost:3000/generate/chat?surface=home
http://localhost:3000/generate/chat?surface=studio
http://localhost:3000/generate/chat?surface=reference
http://localhost:3000/generate/chat?surface=ads
http://localhost:3000/generate/chat?surface=brand
http://localhost:3000/generate/chat?surface=chat
```

Chat generation sub-state uses an optional `stage` query parameter:

```text
http://localhost:3000/generate/chat?surface=chat&stage=start
http://localhost:3000/generate/chat?surface=chat&stage=brief
http://localhost:3000/generate/chat?surface=chat&stage=generating
http://localhost:3000/generate/chat?surface=chat&stage=complete
http://localhost:3000/generate/chat?surface=chat&stage=similar
```

Rules:

- Missing `surface` defaults to `home`.
- Invalid `surface` defaults to `home`.
- Missing `stage` defaults to `start`.
- Invalid `stage` defaults to `start`.
- Bottom nav tabs call `router.push()` so browser back/forward follows user navigation.
- Internal chat step transitions may keep reducer state, but final visible surface should always match the current URL.

## Problem-to-Task Map

- Direct review addresses and browser history: Tasks 1, 2, and 9.
- `스튜디오` tab as its own entry screen: Tasks 2 and 9 keep `surface=studio` mapped to `StudioEntryStep`.
- Placeholder-looking cards: Tasks 3 and 4.
- Missing save/edit/status feedback: Tasks 5 and 8.
- Emoji, small touch targets, weak focus states, and motion preferences: Tasks 6 and 7.
- Final 390x844, 375x667, and 430x932 review: Task 10.

## File Structure

Create:

- `apps/web/lib/dashboard-navigation.ts`
  - Owns valid surface/stage values, parser helpers, and URL builders.
- `apps/web/lib/mock-dashboard-data.ts`
  - Owns mock reference cards, recent ads, recommendation cards, brand facts, and UI copy used across dashboard screens.
- `apps/web/components/generate/AdCreativeCard.tsx`
  - Reusable visual card for reference/result/recent/recommendation ads.
- `apps/web/components/generate/DashboardToast.tsx`
  - Small non-blocking feedback banner for save/edit/regenerate mock actions.

Modify:

- `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Read/write `surface` and `stage` query params.
  - Centralize navigation handlers.
  - Show feedback when mock actions are tapped.
- `apps/web/components/generate/HomeStartStep.tsx`
  - Match dashboard reference more closely and use query-backed navigation callbacks.
- `apps/web/components/generate/StudioEntryStep.tsx`
  - Keep this as the `스튜디오` tab entry screen.
  - Remove emoji tip icon and use Lucide icon.
- `apps/web/components/generate/ReferenceBrowseStep.tsx`
  - Use `AdCreativeCard`.
  - Add save feedback callback.
  - Keep bottom nav consistent with all dashboard tabs.
- `apps/web/components/generate/RecentAdsStep.tsx`
  - Use richer creative thumbnails.
  - Add `진행 상황 보기` action.
  - Add action feedback.
- `apps/web/components/generate/BrandKitStep.tsx`
  - Use richer recommendation thumbnails.
  - Confirm active bottom tab behavior.
- `apps/web/components/generate/GenerationCompleteStep.tsx`
  - Use `AdCreativeCard`.
  - Add action feedback for save/edit/regenerate/similar.
- `apps/web/components/generate/generate.module.css`
  - Add semantic design tokens.
  - Add focus-visible styles.
  - Normalize touch target sizes.
  - Add card visual styles and press feedback.
  - Add reduced-motion handling.
- `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
  - Add unit tests for URL-backed navigation and feedback.
- `apps/web/e2e/chat-start.spec.ts`
  - Add deep-link tests for dashboard surfaces.
- `apps/web/README.md`
  - Document direct review addresses and testing commands.

---

### Task 1: Add Query-Backed Navigation Helpers

**Files:**
- Create: `apps/web/lib/dashboard-navigation.ts`
- Test: `apps/web/lib/dashboard-navigation.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `apps/web/lib/dashboard-navigation.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  buildDashboardHref,
  parseDashboardStage,
  parseDashboardSurface,
  type DashboardStage,
  type DashboardSurface
} from "./dashboard-navigation";

describe("dashboard navigation helpers", () => {
  it("defaults unknown surfaces and stages to safe values", () => {
    expect(parseDashboardSurface(null)).toBe("home");
    expect(parseDashboardSurface("unknown")).toBe("home");
    expect(parseDashboardStage(null)).toBe("start");
    expect(parseDashboardStage("unknown")).toBe("start");
  });

  it("accepts every supported dashboard surface", () => {
    const surfaces: DashboardSurface[] = ["home", "studio", "reference", "ads", "brand", "chat"];

    expect(surfaces.map((surface) => parseDashboardSurface(surface))).toEqual(surfaces);
  });

  it("accepts every supported chat stage", () => {
    const stages: DashboardStage[] = ["start", "brief", "generating", "complete", "similar"];

    expect(stages.map((stage) => parseDashboardStage(stage))).toEqual(stages);
  });

  it("builds stable review URLs", () => {
    expect(buildDashboardHref("home")).toBe("/generate/chat?surface=home");
    expect(buildDashboardHref("studio")).toBe("/generate/chat?surface=studio");
    expect(buildDashboardHref("chat", "generating")).toBe("/generate/chat?surface=chat&stage=generating");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/web
npm run test -- --run lib/dashboard-navigation.test.ts
```

Expected:

```text
FAIL  lib/dashboard-navigation.test.ts
Error: Failed to resolve import "./dashboard-navigation"
```

- [ ] **Step 3: Implement the navigation helpers**

Create `apps/web/lib/dashboard-navigation.ts`:

```ts
export const dashboardSurfaces = ["home", "studio", "reference", "ads", "brand", "chat"] as const;
export type DashboardSurface = (typeof dashboardSurfaces)[number];

export const dashboardStages = ["start", "brief", "generating", "complete", "similar"] as const;
export type DashboardStage = (typeof dashboardStages)[number];

export function parseDashboardSurface(value: string | null | undefined): DashboardSurface {
  return dashboardSurfaces.includes(value as DashboardSurface) ? (value as DashboardSurface) : "home";
}

export function parseDashboardStage(value: string | null | undefined): DashboardStage {
  return dashboardStages.includes(value as DashboardStage) ? (value as DashboardStage) : "start";
}

export function buildDashboardHref(surface: DashboardSurface, stage?: DashboardStage): string {
  const params = new URLSearchParams({ surface });
  if (stage) {
    params.set("stage", stage);
  }
  return `/generate/chat?${params.toString()}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd apps/web
npm run test -- --run lib/dashboard-navigation.test.ts
```

Expected:

```text
PASS  lib/dashboard-navigation.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/dashboard-navigation.ts apps/web/lib/dashboard-navigation.test.ts
git commit -m "feat(fe): add dashboard navigation helpers"
```

---

### Task 2: Wire Dashboard Surfaces to URLs

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`
- Test: `apps/web/e2e/chat-start.spec.ts`

- [ ] **Step 1: Add failing unit tests for direct surface rendering**

Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`.

Add this mock before importing `ChatGenerateClient` in the test file:

```ts
const mockPush = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
  useSearchParams: () => mockSearchParams
}));
```

Add this test inside the existing `describe("ChatGenerateClient", () => {` block:

```ts
it("renders dashboard surfaces from query params", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  mockSearchParams = new URLSearchParams("surface=studio");
  const { rerender } = render(<ChatGenerateClient />);
  expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

  mockSearchParams = new URLSearchParams("surface=reference");
  rerender(<ChatGenerateClient />);
  expect(screen.getByText("REFERENCE GALLERY")).toBeTruthy();

  mockSearchParams = new URLSearchParams("surface=ads");
  rerender(<ChatGenerateClient />);
  expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

  mockSearchParams = new URLSearchParams("surface=brand");
  rerender(<ChatGenerateClient />);
  expect(screen.getByText("추천 & 브랜드 키트")).toBeTruthy();
});
```

Add this test:

```ts
it("pushes stable URLs when top-level tabs are selected", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  mockSearchParams = new URLSearchParams("surface=home");
  render(<ChatGenerateClient />);

  fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
  expect(mockPush).toHaveBeenCalledWith("/generate/chat?surface=studio");

  fireEvent.click(screen.getByRole("button", { name: /레퍼런스/ }));
  expect(mockPush).toHaveBeenCalledWith("/generate/chat?surface=reference");
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected:

```text
FAIL  ChatGenerateClient > renders dashboard surfaces from query params
```

- [ ] **Step 3: Implement URL-backed surface state**

Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`.

Add imports:

```ts
import { useEffect, useRef, useReducer, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  buildDashboardHref,
  parseDashboardStage,
  parseDashboardSurface,
  type DashboardStage,
  type DashboardSurface
} from "@/lib/dashboard-navigation";
```

Replace the local `AppSurface` type with the imported `DashboardSurface`.

Inside `ChatGenerateClient`, add:

```ts
const router = useRouter();
const searchParams = useSearchParams();
const appSurface = parseDashboardSurface(searchParams.get("surface"));
const dashboardStage = parseDashboardStage(searchParams.get("stage"));
const lastPrimedStageRef = useRef<string | null>(null);

function navigateTo(surface: DashboardSurface, stage?: DashboardStage) {
  router.push(buildDashboardHref(surface, stage));
}
```

Remove this state:

```ts
const [appSurface, setAppSurface] = useState<AppSurface>("home");
```

Replace every `setAppSurface("home")` with:

```ts
navigateTo("home");
```

Replace every `setAppSurface("studio")` with:

```ts
navigateTo("studio");
```

Replace every `setAppSurface("referenceGallery")` with:

```ts
navigateTo("reference");
```

Replace every `setAppSurface("recentAds")` with:

```ts
navigateTo("ads");
```

Replace every `setAppSurface("brandKit")` with:

```ts
navigateTo("brand");
```

Replace `handleOpenFreshChat` with:

```ts
function handleOpenFreshChat() {
  dispatch({ type: "reset" });
  setGenerationProgress(0);
  setGenerationStage("brief");
  navigateTo("chat", "start");
}
```

Add this effect so direct chat-stage URLs render useful mock screens without requiring the user to click through the whole flow:

```ts
useEffect(() => {
  if (appSurface !== "chat") {
    lastPrimedStageRef.current = null;
    return;
  }

  if (dashboardStage === "start") {
    if (lastPrimedStageRef.current === "start") {
      return;
    }
    dispatch({ type: "reset" });
    setGenerationProgress(0);
    setGenerationStage("brief");
    lastPrimedStageRef.current = "start";
    return;
  }

  if (lastPrimedStageRef.current === dashboardStage) {
    return;
  }

  dispatch({ type: "reset" });
  dispatch({ type: "submitPrompt", prompt: "삼겹살집 회식 손님 많이 오게 포스터 만들어줘" });
  dispatch({ type: "continueToCopy" });
  dispatch({ type: "continueToBrief" });
  setGenerationProgress(dashboardStage === "generating" ? 68 : 100);
  setGenerationStage(
    dashboardStage === "generating"
      ? "generating"
      : dashboardStage === "similar"
        ? "similarBrowsing"
        : "complete"
  );
  lastPrimedStageRef.current = dashboardStage;
}, [appSurface, dashboardStage]);
```

Replace render checks by changing the string literals only:

```text
referenceGallery -> reference
recentAds -> ads
brandKit -> brand
```

Use `dashboardStage` when direct-linking to a chat stage:

```tsx
{appSurface === "chat" && dashboardStage === "generating" ? (
  <GenerationInProgressStep state={state} progress={Math.max(generationProgress, 68)} onBrowse={() => navigateTo("chat", "similar")} />
) : null}
```

Update chat stage transitions to push canonical URLs:

```ts
function handleStartMockGeneration() {
  setGenerationProgress(12);
  setGenerationStage("generating");
  navigateTo("chat", "generating");
}

function handleBackFromBrief() {
  setGenerationStage("brief");
  dispatch({ type: "back" });
  navigateTo("chat", "brief");
}
```

When generation reaches 100%, update the URL:

```ts
if (nextProgress >= 100) {
  window.clearInterval(timer);
  setGenerationStage("complete");
  navigateTo("chat", "complete");
}
```

- [ ] **Step 4: Add Playwright deep-link test**

Modify `apps/web/e2e/chat-start.spec.ts`.

Add:

```ts
test("dashboard surfaces are directly addressable", async ({ page }) => {
  await page.goto("/generate/chat?surface=studio");
  await expect(page.getByText("어떻게 시작할까요?")).toBeVisible();

  await page.goto("/generate/chat?surface=reference");
  await expect(page.getByText("REFERENCE GALLERY")).toBeVisible();

  await page.goto("/generate/chat?surface=ads");
  await expect(page.getByText("내 찰떡 광고")).toBeVisible();

  await page.goto("/generate/chat?surface=brand");
  await expect(page.getByText("추천 & 브랜드 키트")).toBeVisible();

  await page.goto("/generate/chat?surface=chat&stage=complete");
  await expect(page.getByText("광고 시안 생성 완료")).toBeVisible();
});
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
npm run e2e
```

Expected:

```text
Test Files  1 passed
8+ passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/e2e/chat-start.spec.ts
git commit -m "feat(fe): support dashboard deep links"
```

---

### Task 3: Centralize Mock Dashboard Data

**Files:**
- Create: `apps/web/lib/mock-dashboard-data.ts`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/BrandKitStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`

- [ ] **Step 1: Create the shared mock data file**

Create `apps/web/lib/mock-dashboard-data.ts`:

```ts
export type CreativeTone = "strawberry" | "mint" | "cream" | "sunny" | "peach";

export type MockCreative = {
  id: string;
  title: string;
  subtitle: string;
  format: string;
  date?: string;
  tone: CreativeTone;
  badge?: string;
};

export const referenceCreatives: MockCreative[] = [
  {
    id: "ref-strawberry-poster",
    title: "감성 카페 신메뉴 포스터",
    subtitle: "봄을 닮은 한 잔, 딸기라떼 출시",
    format: "포스터",
    tone: "strawberry",
    badge: "감성 카페"
  },
  {
    id: "ref-review-banner",
    title: "리뷰 이벤트 배너",
    subtitle: "부드러운 색감과 여백이 살아있는 광고 스타일",
    format: "배너",
    tone: "mint",
    badge: "리뷰 이벤트"
  },
  {
    id: "ref-sale-story",
    title: "인스타 스토리",
    subtitle: "여름 시즌 할인 소식을 한눈에 보여주는 시안",
    format: "스토리",
    tone: "sunny",
    badge: "SUMMER SALE"
  },
  {
    id: "ref-spring-sale",
    title: "시즌 할인 포스터",
    subtitle: "봄 시즌 할인 프로모션",
    format: "포스터",
    tone: "peach",
    badge: "SPRING SALE"
  }
];

export const recentCreatives: MockCreative[] = [
  {
    id: "recent-strawberry",
    title: "딸기라떼 신메뉴 광고",
    subtitle: "인스타 피드 (1:1)",
    format: "인스타 피드",
    date: "2024.05.29",
    tone: "strawberry"
  },
  {
    id: "recent-cafe-sale",
    title: "카페 할인 이벤트",
    subtitle: "인스타 스토리 (9:16)",
    format: "인스타 스토리",
    date: "2024.05.25",
    tone: "cream"
  },
  {
    id: "recent-summer",
    title: "여름 시즌 포스터",
    subtitle: "포스터 (4:5)",
    format: "포스터",
    date: "2024.05.20",
    tone: "mint"
  }
];

export const resultCreatives: MockCreative[] = [
  {
    id: "result-1",
    title: "봄을 닮은 한 잔",
    subtitle: "오늘 저녁, 따뜻한 딸기라떼 한 잔",
    format: "1:1",
    tone: "strawberry"
  },
  {
    id: "result-2",
    title: "New Strawberry Latte",
    subtitle: "상큼한 신메뉴 출시",
    format: "1:1",
    tone: "peach"
  },
  {
    id: "result-3",
    title: "딸기 한가득 오늘의 신메뉴",
    subtitle: "매일 한정 수량",
    format: "4:5",
    tone: "cream"
  },
  {
    id: "result-4",
    title: "STRAWBERRY LATTE",
    subtitle: "부드럽고 산뜻한 시즌 메뉴",
    format: "1:1",
    tone: "mint"
  }
];

export const brandFacts = {
  name: "도민 카페",
  status: "사용 중",
  meta: "카페 · 성수동 감성 상권 · @domin_cafe",
  tone: "감성적인, 따뜻한",
  colors: ["#D7B48B", "#FFD7C9", "#D8A29B"],
  products: "딸기라떼, 바닐라라떼, 크림라떼",
  phrases: "신메뉴 출시, 매일 한정 수량, 예약은 DM"
};
```

- [ ] **Step 2: Replace inline arrays with shared imports**

In `apps/web/components/generate/ReferenceBrowseStep.tsx`, remove:

```ts
const references = [
  { title: "감성 카페 신메뉴 포스터", tone: "pink" },
  { title: "브런치 카페 이벤트 배너", tone: "mint" },
  { title: "카페 할인 프로모션", tone: "cream" },
  { title: "봄 시즌 감성 광고", tone: "coral" }
];
```

Add:

```ts
import { referenceCreatives } from "@/lib/mock-dashboard-data";
```

Use:

```tsx
{referenceCreatives.map((item) => (
  <AdCreativeCard creative={item} key={item.id} onSave={() => onSaveCreative?.(item.title)} />
))}
```

This step also depends on `AdCreativeCard` from Task 4. If implementing task-by-task strictly, add the import and usage in Task 4.

- [ ] **Step 3: Commit shared data**

```bash
git add apps/web/lib/mock-dashboard-data.ts
git commit -m "refactor(fe): centralize dashboard mock data"
```

---

### Task 4: Build Realistic Mock Creative Cards

**Files:**
- Create: `apps/web/components/generate/AdCreativeCard.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/BrandKitStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write a failing test for richer creative cards**

Add to `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`:

```ts
it("shows realistic creative labels in reference cards", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  mockSearchParams = new URLSearchParams("surface=reference");
  render(<ChatGenerateClient />);

  expect(screen.getByText("SPRING SALE")).toBeTruthy();
  expect(screen.getByText("SUMMER SALE")).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected:

```text
FAIL  shows realistic creative labels in reference cards
```

- [ ] **Step 3: Create `AdCreativeCard`**

Create `apps/web/components/generate/AdCreativeCard.tsx`:

```tsx
"use client";

import { Bookmark } from "lucide-react";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type AdCreativeCardProps = {
  creative: MockCreative;
  index?: number;
  compact?: boolean;
  onSave?: () => void;
};

export function AdCreativeCard({ creative, index, compact = false, onSave }: AdCreativeCardProps) {
  return (
    <article className={styles.adCreativeCard} data-tone={creative.tone} data-compact={compact}>
      {typeof index === "number" ? <strong className={styles.adCreativeNumber}>{index + 1}</strong> : null}
      <button aria-label={`${creative.title} 저장`} className={styles.adCreativeSaveButton} type="button" onClick={onSave}>
        <Bookmark size={15} aria-hidden="true" />
      </button>
      <div className={styles.adCreativeVisual} aria-hidden="true">
        <span className={styles.adCreativeCup} />
        <span className={styles.adCreativeFruit} />
      </div>
      <div className={styles.adCreativeCopy}>
        {creative.badge ? <em>{creative.badge}</em> : null}
        <h2>{creative.title}</h2>
        <p>{creative.subtitle}</p>
      </div>
    </article>
  );
}
```

- [ ] **Step 4: Add card CSS**

Append to `apps/web/components/generate/generate.module.css`:

```css
.adCreativeCard {
  position: relative;
  min-height: 158px;
  border: 1px solid rgba(17, 17, 17, 0.1);
  border-radius: 13px;
  overflow: hidden;
  padding: 10px;
  display: grid;
  align-content: space-between;
  background: #fff7ef;
}

.adCreativeCard[data-tone="strawberry"] {
  background: linear-gradient(145deg, #ffe2df, #fff4ec);
}

.adCreativeCard[data-tone="mint"] {
  background: linear-gradient(145deg, #e2f5ec, #fffaf0);
}

.adCreativeCard[data-tone="cream"] {
  background: linear-gradient(145deg, #f4efe4, #fff8ed);
}

.adCreativeCard[data-tone="sunny"] {
  background: linear-gradient(145deg, #ffd05a, #fff1b8);
}

.adCreativeCard[data-tone="peach"] {
  background: linear-gradient(145deg, #ffd8d1, #fff0ea);
}

.adCreativeSaveButton {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(17, 17, 17, 0.14);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.82);
  color: var(--color-text);
}

.adCreativeVisual {
  min-height: 72px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.adCreativeCup {
  width: 58px;
  height: 68px;
  border-radius: 16px 16px 22px 22px;
  background:
    radial-gradient(circle at 34% 12%, #fff 0 8px, transparent 9px),
    linear-gradient(180deg, #fff 0 26%, rgba(255, 108, 91, 0.68) 27% 100%);
  box-shadow: 0 10px 22px rgba(159, 63, 47, 0.14);
}

.adCreativeFruit {
  position: absolute;
  right: 52px;
  top: 44px;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #ff6b62;
  box-shadow: 18px -8px 0 -1px #ff6b62, -10px 28px 0 -2px #ff8b82;
}

.adCreativeCopy em {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  padding: 4px 7px;
  color: #5a4a35;
  font-style: normal;
  font-size: 10px;
  font-weight: 900;
}

.adCreativeCopy h2 {
  margin: 7px 0 0;
  max-width: 112px;
  font-size: 13px;
  line-height: 1.25;
  font-weight: 950;
}

.adCreativeCopy p {
  margin: 6px 0 0;
  max-width: 132px;
  color: rgba(17, 17, 17, 0.68);
  font-size: 10px;
  line-height: 1.35;
  font-weight: 800;
}

.adCreativeNumber {
  position: absolute;
  left: 8px;
  top: 8px;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: #111;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 950;
}
```

- [ ] **Step 5: Use `AdCreativeCard` in reference and result screens**

In `ReferenceBrowseStep.tsx`, import:

```ts
import { referenceCreatives } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
```

Replace the current reference card map with:

```tsx
{referenceCreatives.map((item) => (
  <AdCreativeCard creative={item} key={item.id} onSave={() => onSaveCreative?.(item.title)} />
))}
```

In `GenerationCompleteStep.tsx`, import:

```ts
import { resultCreatives } from "@/lib/mock-dashboard-data";
import { AdCreativeCard } from "./AdCreativeCard";
```

Replace the current `mockCreatives.map` block with:

```tsx
{resultCreatives.map((creative, index) => (
  <AdCreativeCard creative={creative} index={index} key={creative.id} onSave={() => onSaveCreative?.(creative.title)} />
))}
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
npm run e2e
```

Expected:

```text
PASS
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/generate/AdCreativeCard.tsx apps/web/components/generate/ReferenceBrowseStep.tsx apps/web/components/generate/GenerationCompleteStep.tsx apps/web/components/generate/generate.module.css apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(fe): add realistic mock creative cards"
```

---

### Task 5: Add Toast Feedback for Mock Actions

**Files:**
- Create: `apps/web/components/generate/DashboardToast.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write a failing feedback test**

Add to `ChatGenerateClient.test.tsx`:

```ts
it("shows feedback when a mock creative is saved", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  mockSearchParams = new URLSearchParams("surface=reference");
  render(<ChatGenerateClient />);

  fireEvent.click(screen.getByLabelText("감성 카페 신메뉴 포스터 저장"));

  expect(screen.getByText("감성 카페 신메뉴 포스터를 보관함에 저장했어요.")).toBeTruthy();
});
```

- [ ] **Step 2: Create toast component**

Create `apps/web/components/generate/DashboardToast.tsx`:

```tsx
"use client";

import { CheckCircle2 } from "lucide-react";
import styles from "./generate.module.css";

type DashboardToastProps = {
  message: string | null;
};

export function DashboardToast({ message }: DashboardToastProps) {
  if (!message) {
    return null;
  }

  return (
    <div className={styles.dashboardToast} role="status" aria-live="polite">
      <CheckCircle2 size={17} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
```

- [ ] **Step 3: Add toast state to client**

Modify `ChatGenerateClient.tsx`:

```ts
import { DashboardToast } from "@/components/generate/DashboardToast";
```

Inside `ChatGenerateClient`:

```ts
const [toastMessage, setToastMessage] = useState<string | null>(null);

function showToast(message: string) {
  setToastMessage(message);
  window.setTimeout(() => setToastMessage(null), 3000);
}
```

Render toast once inside `MobileShell`, preferably as the last child:

```tsx
<DashboardToast message={toastMessage} />
```

Pass callbacks:

```tsx
<ReferenceBrowseStep
  state={state}
  progress={generationProgress}
  isStandaloneGallery
  onGoHome={() => navigateTo("home")}
  onOpenReference={() => navigateTo("reference")}
  onOpenStudio={() => navigateTo("studio")}
  onOpenRecentAds={() => navigateTo("ads")}
  onOpenBrandKit={() => navigateTo("brand")}
  onShowProgress={() => navigateTo("studio")}
  onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
/>;
```

```tsx
<GenerationCompleteStep
  state={state}
  onBrowseSimilar={() => navigateTo("chat", "similar")}
  onGoHome={() => navigateTo("home")}
  onRegenerate={handleStartMockGeneration}
  onSaveCreative={(title) => showToast(`${title}를 보관함에 저장했어요.`)}
  onEditCreative={() => showToast("선택한 시안 편집 화면은 곧 연결됩니다.")}
/>;
```

- [ ] **Step 4: Add toast CSS**

Append to `generate.module.css`:

```css
.dashboardToast {
  position: sticky;
  bottom: 12px;
  z-index: 20;
  min-height: 44px;
  margin: 12px 0 0;
  border: 1px solid rgba(105, 209, 184, 0.5);
  border-radius: 14px;
  background: #e8fbf5;
  color: #24564b;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.4;
  font-weight: 850;
  box-shadow: 0 12px 28px rgba(17, 17, 17, 0.08);
}
```

- [ ] **Step 5: Run tests**

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
```

Expected:

```text
PASS
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/generate/DashboardToast.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/components/generate/ReferenceBrowseStep.tsx apps/web/components/generate/GenerationCompleteStep.tsx apps/web/components/generate/generate.module.css apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(fe): add dashboard mock action feedback"
```

---

### Task 6: Replace Emoji UI Symbols with Lucide Icons

**Files:**
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
- Modify: `apps/web/components/generate/StudioEntryStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Find emoji usage**

Run:

```bash
rg -n "✨|💡|😊|🎉|👋" apps/web/components/generate apps/web/app/generate
```

Expected current matches include strings such as:

```text
StudioEntryStep.tsx
RecentAdsStep.tsx
```

- [ ] **Step 2: Replace tip emoji with icon**

Modify `StudioEntryStep.tsx`.

Add import:

```ts
import { Lightbulb } from "lucide-react";
```

Replace:

```tsx
<p className={styles.studioTip}>
  💡 어떤 방식이든 AI가 광고 브리프를 만들고 찰떡같은 광고 이미지를 제안해드려요.
</p>
```

with:

```tsx
<p className={styles.studioTip}>
  <Lightbulb size={17} aria-hidden="true" />
  <span>어떤 방식이든 AI가 광고 브리프를 만들고 찰떡같은 광고 이미지를 제안해드려요.</span>
</p>
```

- [ ] **Step 3: Replace status emoji with icon**

Modify `RecentAdsStep.tsx`.

Add import:

```ts
import { Smile } from "lucide-react";
```

Replace:

```tsx
<small>생성 중… 잠시만 기다려주세요 😊</small>
```

with:

```tsx
<small>
  생성 중… 잠시만 기다려주세요 <Smile size={12} aria-hidden="true" />
</small>
```

- [ ] **Step 4: Update CSS for inline icons**

Append:

```css
.studioTip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.inProgressAd small {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
```

- [ ] **Step 5: Verify no structural emojis remain**

Run:

```bash
rg -n "✨|💡|😊|🎉|👋" apps/web/components/generate apps/web/app/generate
```

Expected:

```text
No output
```

If `✨` remains inside marketing copy, replace it with `<Sparkles />` next to the text.

- [ ] **Step 6: Run tests and commit**

```bash
cd apps/web
npm run lint
npm run test -- --run
git add apps/web/components/generate apps/web/app/generate
git commit -m "fix(fe): replace structural emoji with icons"
```

---

### Task 7: Normalize Touch Targets, Focus, Reduced Motion, and Tokens

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/components/generate/generate.module.css`
- Test: `apps/web/e2e/chat-start.spec.ts`

- [ ] **Step 1: Add accessibility baseline CSS**

Modify `apps/web/app/globals.css`.

Add:

```css
:focus-visible {
  outline: 3px solid rgba(170, 146, 255, 0.9);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Add dashboard semantic tokens**

Modify `apps/web/components/generate/generate.module.css` near the top.

Add:

```css
.phone {
  --dashboard-lime: #eaff79;
  --dashboard-lime-soft: #f5ffd0;
  --dashboard-mint: #dff8f2;
  --dashboard-mint-border: #bcebe2;
  --dashboard-peach: #fff0ea;
  --dashboard-purple-soft: #eee8ff;
  --dashboard-card-radius: 14px;
  --dashboard-section-gap: 18px;
}
```

- [ ] **Step 3: Normalize touch target sizes**

Add:

```css
.bottomTabs button,
.categoryScroller button,
.recentAdItem div div button,
.editActionGrid button,
.resultChips span {
  min-height: 44px;
}

.adCreativeSaveButton,
.galleryTopBar button,
.dashboardHeader button,
.studioTopNav button,
.recentHeader button,
.iconButton {
  min-width: 44px;
  min-height: 44px;
}

button {
  touch-action: manipulation;
}
```

- [ ] **Step 4: Add press feedback without layout shift**

Add:

```css
.quickDashboardGrid button,
.studioOptionCard,
.brandNoticeCard,
.primaryButton,
.secondaryButton,
.adCreativeCard {
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    background-color 180ms ease,
    box-shadow 180ms ease;
}

.quickDashboardGrid button:active,
.studioOptionCard:active,
.brandNoticeCard:active,
.primaryButton:active,
.secondaryButton:active,
.adCreativeCard:active {
  transform: scale(0.98);
}
```

- [ ] **Step 5: Add Playwright focus test**

Modify `apps/web/e2e/chat-start.spec.ts`.

Add:

```ts
test("keyboard focus is visible on dashboard controls", async ({ page }) => {
  await page.goto("/generate/chat?surface=home");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus-visible")).toBeVisible();
});
```

- [ ] **Step 6: Run tests**

```bash
cd apps/web
npm run e2e
npm run lint
```

Expected:

```text
All tests pass
```

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/globals.css apps/web/components/generate/generate.module.css apps/web/e2e/chat-start.spec.ts
git commit -m "fix(fe): improve dashboard accessibility states"
```

---

### Task 8: Add Missing Dashboard Actions

**Files:**
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/BrandKitStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add failing action tests**

Add to `ChatGenerateClient.test.tsx`:

```ts
it("shows feedback for recent ad and brand kit actions", async () => {
  (globalThis as typeof globalThis & { React: typeof React }).React = React;
  const { ChatGenerateClient } = await import("./ChatGenerateClient");

  mockSearchParams = new URLSearchParams("surface=ads");
  const { rerender } = render(<ChatGenerateClient />);

  fireEvent.click(screen.getByRole("button", { name: "진행 상황 보기" }));
  expect(screen.getByText("딸기라떼 신메뉴 광고 생성 상태를 확인합니다.")).toBeTruthy();

  mockSearchParams = new URLSearchParams("surface=brand");
  rerender(<ChatGenerateClient />);
  fireEvent.click(screen.getByRole("button", { name: /수정하기/ }));
  expect(screen.getByText("브랜드 키트 수정 화면은 곧 연결됩니다.")).toBeTruthy();
});
```

- [ ] **Step 2: Add props to RecentAdsStep**

Modify `RecentAdsStep.tsx` props:

```ts
type RecentAdsStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenBrandKit: () => void;
  onRegenerate: () => void;
  onShowProgress: () => void;
  onOpenAd: (title: string) => void;
};
```

Add button in the generating card:

```tsx
<button className={styles.statusButton} type="button" onClick={onShowProgress}>
  진행 상황 보기
</button>
```

Update `다시 보기`:

```tsx
<button type="button" onClick={() => onOpenAd(ad.title)}>다시 보기</button>
```

- [ ] **Step 3: Add props to BrandKitStep**

Modify `BrandKitStep.tsx` props:

```ts
type BrandKitStepProps = {
  onGoHome: () => void;
  onOpenReference: () => void;
  onOpenStudio: () => void;
  onOpenRecentAds: () => void;
  onEditBrandKit: () => void;
};
```

Update the 수정하기 button:

```tsx
<button type="button" onClick={onEditBrandKit}>수정하기 ›</button>
```

- [ ] **Step 4: Connect callbacks in client**

Modify `ChatGenerateClient.tsx`:

```tsx
<RecentAdsStep
  onGoHome={() => navigateTo("home")}
  onOpenReference={() => navigateTo("reference")}
  onOpenStudio={() => navigateTo("studio")}
  onOpenBrandKit={() => navigateTo("brand")}
  onRegenerate={handleRegenerateFromRecent}
  onShowProgress={() => showToast("딸기라떼 신메뉴 광고 생성 상태를 확인합니다.")}
  onOpenAd={(title) => showToast(`${title} 상세 화면은 곧 연결됩니다.`)}
/>;
```

```tsx
<BrandKitStep
  onGoHome={() => navigateTo("home")}
  onOpenReference={() => navigateTo("reference")}
  onOpenStudio={() => navigateTo("studio")}
  onOpenRecentAds={() => navigateTo("ads")}
  onEditBrandKit={() => showToast("브랜드 키트 수정 화면은 곧 연결됩니다.")}
/>;
```

- [ ] **Step 5: Add CSS for status button**

Add:

```css
.statusButton {
  min-height: 34px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text);
  padding: 0 10px;
  font-size: 11px;
  font-weight: 900;
}
```

- [ ] **Step 6: Run tests and commit**

```bash
cd apps/web
npm run test -- --run app/generate/chat/ChatGenerateClient.test.tsx
npm run e2e
git add apps/web/app/generate/chat/ChatGenerateClient.tsx apps/web/components/generate/RecentAdsStep.tsx apps/web/components/generate/BrandKitStep.tsx apps/web/components/generate/generate.module.css apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(fe): add dashboard mock action feedback"
```

---

### Task 9: Document Review URLs and Run Commands

**Files:**
- Modify: `apps/web/README.md`

- [ ] **Step 1: Add direct review URL section**

Add this section to `apps/web/README.md` after "모바일 기준으로 확인하기":

```md
## 대시보드 화면 직접 확인 주소

Web dev server:

```bash
cd apps/web
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

Open:

```text
http://localhost:3000/generate/chat?surface=home
http://localhost:3000/generate/chat?surface=studio
http://localhost:3000/generate/chat?surface=reference
http://localhost:3000/generate/chat?surface=ads
http://localhost:3000/generate/chat?surface=brand
http://localhost:3000/generate/chat?surface=chat
http://localhost:3000/generate/chat?surface=chat&stage=generating
http://localhost:3000/generate/chat?surface=chat&stage=complete
```

Primary mobile review viewport:

```text
390x844
```

Small and large checks:

```text
375x667
430x932
```
```

- [ ] **Step 2: Verify markdown renders**

Run:

```bash
sed -n '1,240p' apps/web/README.md
```

Expected:

```text
The new direct review URL section appears once.
All fenced code blocks close correctly.
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/README.md
git commit -m "docs(fe): document dashboard review URLs"
```

---

### Task 10: Final Verification and Screenshot Review

**Files:**
- No source files should change in this task unless verification exposes a defect.

- [ ] **Step 1: Run full frontend validation**

Run:

```bash
cd apps/web
npm run test -- --run
npm run lint
npm run build
```

Expected:

```text
All tests pass.
No ESLint warnings or errors.
next build exits 0.
```

- [ ] **Step 2: Restart dev server cleanly before E2E**

If port `3000` is occupied by an old Next server, stop it:

```bash
ss -ltnp 'sport = :3000'
```

If a `next-server` process is shown, stop only that web dev process:

```bash
kill <pid>
```

Run:

```bash
cd apps/web
npm run e2e
```

Expected:

```text
All Playwright tests pass.
```

- [ ] **Step 3: Start dev server for manual review**

Run:

```bash
cd apps/web
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4000 npm run dev
```

Expected:

```text
Local: http://localhost:3000
```

- [ ] **Step 4: Capture 390x844 screenshots**

Run:

```bash
cd apps/web
node - <<'NODE'
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true });
  const surfaces = ["home", "studio", "reference", "ads", "brand"];

  for (const surface of surfaces) {
    await page.goto(`http://127.0.0.1:3000/generate/chat?surface=${surface}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: `/tmp/easyads-${surface}-polished.png`, fullPage: false });
  }

  await browser.close();
})();
NODE
```

Expected files:

```text
/tmp/easyads-home-polished.png
/tmp/easyads-studio-polished.png
/tmp/easyads-reference-polished.png
/tmp/easyads-ads-polished.png
/tmp/easyads-brand-polished.png
```

- [ ] **Step 5: Manual UI checklist**

Open the screenshots and confirm:

```text
Home: CTA, quick start cards, brand notice, bottom nav visible without overlap.
Studio: 3 entry cards fit in 390x844 and bottom nav is visible.
Reference: cards look like ad creatives, not blank placeholders.
Ads: progress card has a visible "진행 상황 보기" action.
Brand: recommendation cards and brand kit card fit without horizontal overflow.
All: bottom nav has 5 items, active state is visible, tap targets are not cramped.
```

- [ ] **Step 6: Final commit if verification required fixes**

If fixes were needed:

```bash
git add apps/web
git commit -m "fix(fe): polish dashboard verification issues"
```

If no fixes were needed:

```bash
git status --short
```

Expected:

```text
Only unrelated untracked images/ remain, or working tree is clean.
```

---

## Self-Review

- Spec coverage: The plan covers address/deep-link setup, visual fidelity, mock card assets, touch targets, emoji replacement, feedback states, docs, and final verification.
- Placeholder scan: No red-flag placeholder phrases or undefined future-only task steps are present.
- Type consistency: `DashboardSurface`, `DashboardStage`, `MockCreative`, and callback prop names are defined before use.
- Scope check: This plan stays within the frontend mock dashboard and does not attempt real image generation or backend persistence.
