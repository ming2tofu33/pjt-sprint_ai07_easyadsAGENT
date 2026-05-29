# Onboarding Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four-step first-use onboarding flow from `images/개떡찰떡_앱소개와 랜딩 팝업 생성.png`.

**Architecture:** Add a clean `/onboarding` route family with step-specific deep links. Keep onboarding independent from the authenticated app shell so it can be opened directly for review, while its final actions route into the existing `/studio` and `/brand/kit` flows. Store slide content in a small mock data export and render it through one reusable client component.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS Modules, lucide-react, Vitest, Playwright.

---

## Reference Analysis

The reference has four mobile onboarding screens:

1. **앱 소개**
   - Goal: explain what the service is.
   - Visual structure:
     - Large centered headline: `개떡처럼 말해도, 찰떡같이 광고로.`
     - Short body copy explaining that AI asks and suggests even if the user does not know design.
     - Large friendly illustration area.
     - White feature summary card with three rows:
       - `대충 말해도 OK`
       - `AI가 필요한 정보를 질문`
       - `찰떡 광고 이미지로 완성`
     - Dot pagination.
     - Primary CTA `다음`.
     - Secondary text action `건너뛰기`.

2. **시작 방식 안내**
   - Goal: show the three creation entry points.
   - Visual structure:
     - Headline: `원하는 방식으로 시작하세요`
     - Three large selectable cards:
       - `레퍼런스 보고 만들기`
       - `내 사진으로 만들기`
       - `대화로 시작하기`
     - Each card has a thumbnail/icon and arrow affordance.
     - Dot pagination.
     - Primary CTA `다음`.

3. **AI 브리프 방식**
   - Goal: teach how AI asks questions and proposes copy/brief options.
   - Visual structure:
     - Headline: `AI가 질문하고 제안해 브리프를 완성해요`
     - Mock chat conversation card.
     - Mood chips and copy option cards.
     - Direct input bar.
     - Dot pagination.
     - Primary CTA `다음`.

4. **시작 준비**
   - Goal: choose an immediate next action.
   - Visual structure:
     - Headline: `이제 첫 찰떡 광고를 만들어볼까요?`
     - Two large action cards:
       - `바로 광고 만들기`
       - `브랜드 키트 만들기`
     - Secondary text action `나중에 할게요`.
     - Dot pagination.

## URL Decision

Use route segments instead of query strings:

```text
/onboarding
/onboarding/modes
/onboarding/brief
/onboarding/start
```

Action destinations:

```text
바로 광고 만들기 -> /studio
브랜드 키트 만들기 -> /brand/kit
건너뛰기 / 나중에 할게요 -> /
```

## File Structure

- Create: `apps/web/lib/onboarding-navigation.ts`
  - Builds clean onboarding URLs.
- Create: `apps/web/lib/onboarding-navigation.test.ts`
  - Verifies route construction.
- Modify: `apps/web/lib/mock-dashboard-data.ts`
  - Adds onboarding slide content.
- Create: `apps/web/components/generate/OnboardingFlowStep.tsx`
  - Renders all four onboarding screens by `step` prop.
- Create: `apps/web/app/onboarding/page.tsx`
- Create: `apps/web/app/onboarding/modes/page.tsx`
- Create: `apps/web/app/onboarding/brief/page.tsx`
- Create: `apps/web/app/onboarding/start/page.tsx`
- Modify: `apps/web/components/generate/generate.module.css`
  - Adds onboarding hero, feature rows, mode cards, chat demo, and final action styles.
- Modify: `apps/web/README.md`
  - Adds onboarding URLs.
- Modify: `apps/web/e2e/chat-start.spec.ts`
  - Adds route and CTA coverage.

---

### Task 1: Onboarding Navigation Helper

**Files:**
- Create: `apps/web/lib/onboarding-navigation.ts`
- Create: `apps/web/lib/onboarding-navigation.test.ts`

- [ ] **Step 1: Write route helper test**

```ts
import { describe, expect, it } from "vitest";
import { buildOnboardingHref } from "./onboarding-navigation";

describe("onboarding navigation", () => {
  it("builds clean onboarding hrefs", () => {
    expect(buildOnboardingHref()).toBe("/onboarding");
    expect(buildOnboardingHref("intro")).toBe("/onboarding");
    expect(buildOnboardingHref("modes")).toBe("/onboarding/modes");
    expect(buildOnboardingHref("brief")).toBe("/onboarding/brief");
    expect(buildOnboardingHref("start")).toBe("/onboarding/start");
  });
});
```

- [ ] **Step 2: Add helper implementation**

```ts
export type OnboardingStep = "intro" | "modes" | "brief" | "start";

export function buildOnboardingHref(step: OnboardingStep = "intro"): string {
  if (step === "intro") {
    return "/onboarding";
  }

  return `/onboarding/${step}`;
}
```

- [ ] **Step 3: Run focused test**

```bash
cd apps/web
npm run test -- --run lib/onboarding-navigation.test.ts
```

Expected: PASS.

### Task 2: Mock Onboarding Data

**Files:**
- Modify: `apps/web/lib/mock-dashboard-data.ts`

- [ ] **Step 1: Add structured content**

Add:

```ts
export const onboardingSlides = {
  intro: {
    title: "개떡처럼 말해도, 찰떡같이 광고로.",
    description: "디자인을 몰라도 괜찮아요. AI가 질문하고 제안하면서 광고 이미지를 만들 준비를 도와드려요.",
    features: [
      { title: "대충 말해도 OK", description: "원하는 광고를 편하게 말해요" },
      { title: "AI가 필요한 정보를 질문", description: "빠진 정보를 AI가 물어봐요" },
      { title: "찰떡 광고 이미지로 완성", description: "완성된 광고를 바로 활용해요" }
    ]
  },
  modes: {
    title: "원하는 방식으로 시작하세요",
    description: "가지고 있는 자료에 따라 가장 편한 방법을 선택할 수 있어요."
  },
  brief: {
    title: "AI가 질문하고 제안해 브리프를 완성해요",
    description: "업종, 상품, 목적, 문구, 분위기, 채널을 대화와 선택지로 자연스럽게 채워요."
  },
  start: {
    title: "이제 첫 찰떡 광고를 만들어볼까요?",
    description: "바로 시작해도 되고, 우리 가게 정보를 먼저 저장해도 좋아요."
  }
};
```

### Task 3: Onboarding Component and Routes

**Files:**
- Create: `apps/web/components/generate/OnboardingFlowStep.tsx`
- Create: `apps/web/app/onboarding/page.tsx`
- Create: `apps/web/app/onboarding/modes/page.tsx`
- Create: `apps/web/app/onboarding/brief/page.tsx`
- Create: `apps/web/app/onboarding/start/page.tsx`

- [ ] **Step 1: Create route pages**

Each page should wrap `OnboardingFlowStep` in `MobileShell`.

```tsx
import { MobileShell } from "@/components/generate/MobileShell";
import { OnboardingFlowStep } from "@/components/generate/OnboardingFlowStep";

export default function OnboardingPage() {
  return (
    <MobileShell>
      <OnboardingFlowStep step="intro" />
    </MobileShell>
  );
}
```

Use `step="modes"`, `step="brief"`, `step="start"` for the nested pages.

- [ ] **Step 2: Implement component**

Interaction requirements:

```ts
intro next -> /onboarding/modes
modes next -> /onboarding/brief
brief next -> /onboarding/start
skip -> /
final ad action -> /studio
final brand kit action -> /brand/kit
```

Use lucide icons only. Icon-only buttons require `aria-label`.

### Task 4: Visual Styling

**Files:**
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add onboarding styles**

Add focused classes:

```css
.onboardingScreen {}
.onboardingHero {}
.onboardingIllustration {}
.onboardingFeatureCard {}
.onboardingModeList {}
.onboardingModeCard {}
.onboardingChatDemo {}
.onboardingFinalActions {}
.onboardingDots {}
.onboardingFooter {}
```

Style expectations:

- Intro background uses soft lime, not a full-screen marketing landing page.
- Modes screen uses three full-width cards with subtle different tones.
- AI brief screen uses a chat card plus option chips to show the interaction model.
- Start screen uses two large action cards, with `바로 광고 만들기` visually primary and `브랜드 키트 만들기` secondary.
- All touch targets are at least 44px high.
- 390x844 is the primary mobile viewport.

### Task 5: Docs and E2E

**Files:**
- Modify: `apps/web/README.md`
- Modify: `apps/web/e2e/chat-start.spec.ts`

- [ ] **Step 1: Add README URLs**

```text
http://localhost:3000/onboarding
http://localhost:3000/onboarding/modes
http://localhost:3000/onboarding/brief
http://localhost:3000/onboarding/start
```

- [ ] **Step 2: Add E2E flow**

```ts
test("onboarding flow reaches app start choices", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  await page.getByRole("button", { name: "다음" }).click();
  await expect(page).toHaveURL(/\/onboarding\/modes$/);
  await expect(page.getByRole("heading", { name: "원하는 방식으로 시작하세요" })).toBeVisible();

  await page.getByRole("button", { name: "다음" }).click();
  await expect(page).toHaveURL(/\/onboarding\/brief$/);
  await expect(page.getByRole("heading", { name: "AI가 질문하고 제안해 브리프를 완성해요" })).toBeVisible();

  await page.getByRole("button", { name: "다음" }).click();
  await expect(page).toHaveURL(/\/onboarding\/start$/);

  await page.getByRole("button", { name: /바로 광고 만들기/ }).click();
  await expect(page).toHaveURL(/\/studio$/);
});
```

Add direct address checks for the four onboarding routes.

### Task 6: Verification

**Files:**
- No edits.

- [ ] **Step 1: Run focused tests**

```bash
cd apps/web
npm run test -- --run lib/onboarding-navigation.test.ts
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

Expected: PASS and route list includes `/onboarding`, `/onboarding/modes`, `/onboarding/brief`, `/onboarding/start`.

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
  ['intro', '/onboarding'],
  ['modes', '/onboarding/modes'],
  ['brief', '/onboarding/brief'],
  ['start', '/onboarding/start'],
];
(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const [name, route] of routes) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true });
    await page.goto(`http://127.0.0.1:3000${route}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: `/tmp/easyads-onboarding-${name}.png`, fullPage: true });
    await page.close();
  }
  await browser.close();
})();
NODE
```

Expected screenshots:

```text
/tmp/easyads-onboarding-intro.png
/tmp/easyads-onboarding-modes.png
/tmp/easyads-onboarding-brief.png
/tmp/easyads-onboarding-start.png
```

## Self-Review

- Spec coverage: all four onboarding screens from the reference are mapped to routes.
- Navigation coverage: next, skip, start-ad, and brand-kit actions have explicit destinations.
- UX coverage: no gesture-only navigation, dot pagination is informational, and each screen keeps one primary next action.
- Testing coverage: route helper test, E2E flow, direct route checks, lint/build, and screenshots are included.
