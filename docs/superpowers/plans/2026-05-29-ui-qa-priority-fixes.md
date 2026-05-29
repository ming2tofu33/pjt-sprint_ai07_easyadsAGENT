# UI QA Priority Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the highest-priority QA issues found in the mobile web app: onboarding keyboard focus, mobile zoom accessibility, first-entry blank state, scroll density, and stale Playwright server reuse.

**Architecture:** Keep the existing Next.js App Router and mobile-shell structure. Add focused regression coverage first, then make small UI and config changes inside the existing `apps/web` boundaries without changing route contracts.

**Tech Stack:** Next.js 14, React, TypeScript, CSS Modules, Vitest, React Testing Library, Playwright.

---

## File Structure

- Modify: `apps/web/components/generate/OnboardingFlowStep.tsx`
  - Responsibility: single-page onboarding carousel interaction, localStorage completion, and route transitions.
  - Change: make inactive slide controls unfocusable and clean up indentation around slide-specific branches.

- Modify: `apps/web/app/layout.tsx`
  - Responsibility: global metadata and viewport configuration.
  - Change: remove `maximumScale: 1` so mobile users can zoom.

- Modify: `apps/web/components/generate/HomeEntryClient.tsx`
  - Responsibility: decide whether `/` should show the dashboard or redirect first-time users to `/onboarding`.
  - Change: render a lightweight mobile loading state while localStorage is checked.

- Modify: `apps/web/components/generate/generate.module.css`
  - Responsibility: all mobile UI styling for the mock app.
  - Change: add the home gate styles and targeted compact rules for dense small-screen routes.

- Modify: `apps/web/playwright.config.ts`
  - Responsibility: Playwright server startup configuration.
  - Change: default to a fresh server unless `PLAYWRIGHT_REUSE_SERVER=1` is explicitly set.

- Modify: `apps/web/e2e/chat-start.spec.ts`
  - Responsibility: end-to-end app flow coverage.
  - Change: add focused assertions for onboarding hidden focus and viewport zoom.

- Create: `apps/web/components/generate/HomeEntryClient.test.tsx`
  - Responsibility: unit-level regression tests for first-entry loading and onboarding redirect.

- Modify: `apps/web/README.md`
  - Responsibility: web app usage and verification instructions.
  - Change: document fresh-server E2E behavior and optional server reuse.

---

### Task 1: Fix Onboarding Hidden Focus

**Files:**
- Modify: `apps/web/e2e/chat-start.spec.ts`
- Modify: `apps/web/components/generate/OnboardingFlowStep.tsx`

- [ ] **Step 1: Add a failing E2E test for inactive onboarding controls**

Add this test after the existing `onboarding flow reaches start choices and studio` test in `apps/web/e2e/chat-start.spec.ts`:

```ts
test("onboarding inactive slides do not expose focusable controls", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name: "개떡처럼 말해도, 찰떡같이 광고로." })).toBeVisible();

  const hiddenFocusable = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[aria-hidden="true"]')).flatMap((hiddenRoot) =>
      Array.from(hiddenRoot.querySelectorAll("button, a[href], input, select, textarea, [tabindex]"))
        .filter((node) => node instanceof HTMLElement && !node.hasAttribute("disabled") && node.tabIndex >= 0)
        .map((node) => (node.textContent || node.getAttribute("aria-label") || node.tagName).trim().replace(/\s+/g, " "))
    )
  );

  expect(hiddenFocusable).toEqual([]);

  await page.keyboard.press("Tab");
  await expect(page.locator(":focus-visible")).toBeVisible();
  await expect(page.getByRole("button", { name: "온보딩 1단계로 이동" })).toBeFocused();
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "onboarding inactive slides do not expose focusable controls" --project=chromium-mobile
```

Expected: FAIL because inactive slide buttons such as `레퍼런스 보고 만들기`, `내 사진으로 만들기`, `바로 광고 만들기`, and `브랜드 키트 만들기` are still tabbable inside `aria-hidden="true"` slides.

- [ ] **Step 3: Make inactive slide buttons unfocusable**

In `apps/web/components/generate/OnboardingFlowStep.tsx`, replace the `renderSlide` function body with this implementation. This keeps all slides mounted for the slide animation, but removes inactive slide actions from the keyboard tab order.

```tsx
  function renderSlide(step: OnboardingStep) {
    const slide = onboardingSlides[step];
    const isActive = step === activeStep;
    const inactiveTabIndex = isActive ? undefined : -1;

    return (
      <article aria-hidden={!isActive} className={styles.onboardingSlide} data-step={step} key={step}>
        <div className={styles.onboardingHero}>
          <h1>{slide.title}</h1>
          <p>{slide.description}</p>
        </div>

        {step === "intro" ? (
          <>
            <div className={styles.onboardingIllustration} aria-hidden="true">
              <span />
              <i />
            </div>
            <section className={styles.onboardingFeatureCard} aria-label="앱 핵심 기능">
              {onboardingSlides.intro.features.map((feature, index) => {
                const icons = [MessageCircle, HelpCircle, ImageIcon];
                const Icon = icons[index];
                return (
                  <article key={feature.title}>
                    <span data-tone={index}>
                      <Icon size={20} aria-hidden="true" />
                    </span>
                    <strong>
                      {feature.title}
                      <small>{feature.description}</small>
                    </strong>
                  </article>
                );
              })}
            </section>
          </>
        ) : null}

        {step === "modes" ? (
          <section className={styles.onboardingModeList} aria-label="시작 방식">
            {modes.map(({ title, description, icon: Icon, tone, href }) => (
              <button
                className={styles.onboardingModeCard}
                data-tone={tone}
                key={title}
                tabIndex={inactiveTabIndex}
                type="button"
                onClick={() => {
                  if (isActive) {
                    router.push(href);
                  }
                }}
              >
                <span>
                  <Icon size={26} aria-hidden="true" />
                </span>
                <strong>
                  {title}
                  <small>{description}</small>
                </strong>
                <ChevronRight size={19} aria-hidden="true" />
              </button>
            ))}
          </section>
        ) : null}

        {step === "brief" ? (
          <section className={styles.onboardingChatDemo} aria-label="AI 브리프 예시">
            <article>
              <span>AI</span>
              <p>어떤 분위기의 광고를 원하시나요?</p>
            </article>
            <div className={styles.onboardingMoodChips}>
              {["감성적인", "상큼한", "고급스러운", "깔끔한"].map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>
            <p className={styles.onboardingUserBubble}>고급스럽고 차분한 느낌이요!</p>
            <article>
              <span>AI</span>
              <p>좋아요. 문구는 이렇게 제안드려요.</p>
            </article>
            <div className={styles.onboardingCopyCards}>
              {copyOptions.map((copy, index) => (
                <span data-active={index === 0 ? "true" : undefined} key={copy}>
                  <b>{index + 1}</b>
                  {copy}
                </span>
              ))}
            </div>
            <div className={styles.onboardingInputPreview}>
              직접 입력도 가능해요
              <Palette size={15} aria-hidden="true" />
            </div>
          </section>
        ) : null}

        {step === "start" ? (
          <section className={styles.onboardingFinalActions} aria-label="시작할 작업 선택">
            <button
              tabIndex={inactiveTabIndex}
              type="button"
              onClick={() => {
                if (isActive) {
                  completeOnboarding(buildDashboardHref("studio"));
                }
              }}
            >
              <span data-tone="ad">
                <WandSparkles size={30} aria-hidden="true" />
              </span>
              <strong>
                바로 광고 만들기
                <small>레퍼런스, 사진, 대화 중 원하는 방식으로 지금 바로 시작해요.</small>
              </strong>
              <ArrowRight size={20} aria-hidden="true" />
            </button>
            <button
              tabIndex={inactiveTabIndex}
              type="button"
              onClick={() => {
                if (isActive) {
                  completeOnboarding(buildBrandKitHref());
                }
              }}
            >
              <span data-tone="brand">
                <Store size={30} aria-hidden="true" />
              </span>
              <strong>
                브랜드 키트 만들기
                <small>가게 이름, 로고, 자주 쓰는 문구를 저장하면 다음 광고가 쉬워져요.</small>
              </strong>
              <ArrowRight size={20} aria-hidden="true" />
            </button>
          </section>
        ) : null}
      </article>
    );
  }
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "onboarding inactive slides do not expose focusable controls" --project=chromium-mobile
```

Expected: PASS.

- [ ] **Step 5: Commit this focused change**

```bash
git add apps/web/e2e/chat-start.spec.ts apps/web/components/generate/OnboardingFlowStep.tsx
git commit -m "fix(web): prevent hidden onboarding controls from receiving focus"
```

---

### Task 2: Allow Mobile Pinch Zoom

**Files:**
- Modify: `apps/web/e2e/chat-start.spec.ts`
- Modify: `apps/web/app/layout.tsx`

- [ ] **Step 1: Add a failing viewport regression test**

Add this test near the existing desktop/mobile-shell checks in `apps/web/e2e/chat-start.spec.ts`:

```ts
test("viewport allows mobile zoom", async ({ page }) => {
  await page.goto("/");

  const viewportContent = await page.locator('meta[name="viewport"]').getAttribute("content");

  expect(viewportContent).toContain("width=device-width");
  expect(viewportContent).toContain("initial-scale=1");
  expect(viewportContent).not.toContain("maximum-scale=1");
  expect(viewportContent).not.toContain("user-scalable=no");
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "viewport allows mobile zoom" --project=chromium-mobile
```

Expected: FAIL because the current viewport meta includes `maximum-scale=1`.

- [ ] **Step 3: Remove the zoom restriction**

Replace the viewport export in `apps/web/app/layout.tsx` with:

```ts
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f8f8f4"
};
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "viewport allows mobile zoom" --project=chromium-mobile
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/e2e/chat-start.spec.ts apps/web/app/layout.tsx
git commit -m "fix(web): allow mobile viewport zoom"
```

---

### Task 3: Replace First-Entry Blank State With Loading UI

**Files:**
- Create: `apps/web/components/generate/HomeEntryClient.test.tsx`
- Modify: `apps/web/components/generate/HomeEntryClient.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Write failing tests for the home entry gate**

Create `apps/web/components/generate/HomeEntryClient.test.tsx`:

```tsx
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";

const navigationMock = vi.hoisted(() => ({
  replace: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: navigationMock.replace
  })
}));

vi.mock("@/app/generate/chat/ChatGenerateClient", () => ({
  ChatGenerateClient: ({ initialSurface }: { initialSurface: string }) => <div>dashboard:{initialSurface}</div>
}));

describe("HomeEntryClient", () => {
  beforeEach(() => {
    window.localStorage.clear();
    navigationMock.replace.mockClear();
  });

  it("shows a mobile loading state before redirecting first-time visitors", async () => {
    const { HomeEntryClient } = await import("./HomeEntryClient");

    render(<HomeEntryClient />);

    expect(screen.getByRole("status")).toHaveTextContent("개떡찰떡을 준비하고 있어요");
    await waitFor(() => expect(navigationMock.replace).toHaveBeenCalledWith("/onboarding"));
  });

  it("renders the home dashboard when onboarding is completed", async () => {
    window.localStorage.setItem(ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE);
    const { HomeEntryClient } = await import("./HomeEntryClient");

    render(<HomeEntryClient />);

    await waitFor(() => expect(screen.getByText("dashboard:home")).toBeTruthy());
    expect(navigationMock.replace).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
cd apps/web
npm run test -- components/generate/HomeEntryClient.test.tsx
```

Expected: FAIL because the component currently returns `null` while deciding.

- [ ] **Step 3: Implement the loading state**

Replace `apps/web/components/generate/HomeEntryClient.tsx` with:

```tsx
"use client";

import { MessageCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ChatGenerateClient } from "@/app/generate/chat/ChatGenerateClient";
import { MobileShell } from "@/components/generate/MobileShell";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";
import styles from "./generate.module.css";

export function HomeEntryClient() {
  const router = useRouter();
  const [canShowHome, setCanShowHome] = useState(false);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(ONBOARDING_COMPLETED_STORAGE_KEY) === ONBOARDING_COMPLETED_VALUE) {
        setCanShowHome(true);
        return;
      }
    } catch {
      setCanShowHome(true);
      return;
    }

    router.replace("/onboarding");
  }, [router]);

  if (!canShowHome) {
    return (
      <MobileShell>
        <section className={styles.homeGate} role="status" aria-live="polite">
          <span className={styles.homeGateMark} aria-hidden="true">
            <MessageCircle size={28} />
          </span>
          <strong>개떡찰떡을 준비하고 있어요</strong>
          <small>처음 방문이면 온보딩으로 안내할게요.</small>
        </section>
      </MobileShell>
    );
  }

  return <ChatGenerateClient initialSurface="home" />;
}
```

- [ ] **Step 4: Add the CSS for the loading state**

Add this block after `.body button` in `apps/web/components/generate/generate.module.css`:

```css
.homeGate {
  flex: 1;
  min-height: 620px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  text-align: center;
}

.homeGateMark {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  background: var(--dashboard-lime-soft);
  color: var(--color-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 14px 30px rgba(176, 203, 32, 0.18);
}

.homeGate strong {
  color: var(--color-text);
  font-size: 18px;
  line-height: 1.3;
  font-weight: 950;
}

.homeGate small {
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.45;
  font-weight: 800;
}
```

- [ ] **Step 5: Run the tests**

Run:

```bash
cd apps/web
npm run test -- components/generate/HomeEntryClient.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/generate/HomeEntryClient.test.tsx apps/web/components/generate/HomeEntryClient.tsx apps/web/components/generate/generate.module.css
git commit -m "fix(web): show loading state during home onboarding gate"
```

---

### Task 4: Reduce Scroll Density On Small Mobile Screens

**Files:**
- Modify: `apps/web/e2e/chat-start.spec.ts`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add a mobile layout budget test**

Add this test after `desktop keeps the app in a centered mobile shell` in `apps/web/e2e/chat-start.spec.ts`:

```ts
test("dense mobile routes stay within scroll budget at 390x844", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  const routes = ["/ads", "/settings", "/generate/chat/complete"];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.getByLabel("개떡찰떡 모바일 화면")).toBeVisible();

    const metrics = await page.evaluate(() => ({
      scrollHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
      overflowX: document.documentElement.scrollWidth - window.innerWidth
    }));

    expect(metrics.overflowX).toBeLessThanOrEqual(1);
    expect(metrics.scrollHeight / metrics.viewportHeight).toBeLessThanOrEqual(1.18);
  }
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "dense mobile routes stay within scroll budget" --project=chromium-mobile
```

Expected: FAIL on `/ads` because the current height ratio is about `1048 / 844 = 1.24`.

- [ ] **Step 3: Add compact CSS for the dense routes**

Append this block near the existing `@media (max-width: 375px)` section in `apps/web/components/generate/generate.module.css`. Put it before the `@media (max-width: 375px)` block so the narrower breakpoint can still override it.

```css
@media (max-width: 390px) {
  .body {
    padding: 24px 16px 18px;
  }

  .archiveFilterRow {
    margin: 12px 0 10px;
    gap: 6px;
  }

  .archiveFilterRow button {
    min-height: 32px;
    padding: 0 10px;
  }

  .archiveGrid {
    gap: 9px;
  }

  .archiveVisual::after {
    right: 20px;
    bottom: 12px;
    width: 46px;
    height: 54px;
  }

  .archiveCopy {
    padding-top: 6px;
  }

  .archiveCopy strong {
    min-height: 28px;
    font-size: 11px;
  }

  .settingsListGroup {
    margin-top: 12px;
    padding: 10px;
  }

  .settingsListGroup button {
    min-height: 44px;
    padding: 6px 0;
  }

  .completeHero {
    margin-top: 10px;
  }

  .completeHero > span {
    width: 48px;
    height: 48px;
  }

  .resultsHeader {
    margin-top: 10px;
  }

  .resultsHeader h1 {
    font-size: 21px;
  }

  .resultChips {
    margin-top: 10px;
    gap: 6px;
  }

  .resultGrid {
    margin-top: 12px;
    gap: 8px;
  }

  .resultCard {
    min-height: 150px;
  }
}
```

- [ ] **Step 4: Run the focused layout test**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "dense mobile routes stay within scroll budget" --project=chromium-mobile
```

Expected: PASS with all three route ratios at or under `1.18`.

- [ ] **Step 5: Run the existing mobile shell regression**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "desktop keeps the app in a centered mobile shell" --project=chromium-desktop
```

Expected: PASS. This ensures compact CSS did not break the desktop-centered mobile frame.

- [ ] **Step 6: Commit**

```bash
git add apps/web/e2e/chat-start.spec.ts apps/web/components/generate/generate.module.css
git commit -m "fix(web): tighten dense mobile layouts"
```

---

### Task 5: Prevent Stale Playwright Server Reuse

**Files:**
- Modify: `apps/web/playwright.config.ts`
- Modify: `apps/web/README.md`

- [ ] **Step 1: Change Playwright to start a fresh server by default**

Replace the `reuseExistingServer` line in `apps/web/playwright.config.ts`:

```ts
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
```

The full `webServer` block should be:

```ts
  webServer: {
    command: "NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4999 npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000
  },
```

- [ ] **Step 2: Document the new behavior**

In `apps/web/README.md`, replace the Playwright E2E section:

```md
Playwright E2E:

```bash
cd apps/web
npm run e2e
```

백엔드 연결까지 확인하려면 orchestrator와 BFF를 먼저 켠 뒤 E2E를 실행합니다.
```

with:

````md
Playwright E2E:

```bash
cd apps/web
npm run e2e
```

E2E는 기본적으로 새 Next.js dev server를 직접 띄웁니다. 3000번 포트에 오래된 서버가 이미 떠 있으면 테스트가 실패할 수 있으니, 아래 명령으로 확인 후 종료하세요.

```bash
ss -ltnp 'sport = :3000'
```

이미 켜둔 서버를 재사용해야 할 때만 명시적으로 실행합니다.

```bash
cd apps/web
PLAYWRIGHT_REUSE_SERVER=1 npm run e2e
```

백엔드 연결까지 확인하려면 orchestrator와 BFF를 먼저 켠 뒤 E2E를 실행합니다.
````

- [ ] **Step 3: Run a smoke E2E command**

Run:

```bash
cd apps/web
npx playwright test e2e/chat-start.spec.ts -g "first visit redirects to onboarding and stores completion" --project=chromium-mobile
```

Expected: PASS. Playwright starts its own server when port 3000 is free.

- [ ] **Step 4: Commit**

```bash
git add apps/web/playwright.config.ts apps/web/README.md
git commit -m "test(web): avoid stale Playwright server reuse"
```

---

### Task 6: Full Verification Pass

**Files:**
- No source files changed in this task.

- [ ] **Step 1: Stop any old server on port 3000**

Run:

```bash
ss -ltnp 'sport = :3000'
```

If a process is listed, stop only the Next.js dev server process that belongs to this project:

```bash
kill <PID_FROM_SS_OUTPUT>
```

Expected: `ss -ltnp 'sport = :3000'` prints only the header or no listening process.

- [ ] **Step 2: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: `✔ No ESLint warnings or errors`.

- [ ] **Step 3: Run unit tests**

Run:

```bash
cd apps/web
npm run test
```

Expected: all Vitest files pass, including `HomeEntryClient.test.tsx`.

- [ ] **Step 4: Run production build**

Run:

```bash
cd apps/web
npm run build
```

Expected: build completes successfully and all app routes are listed.

- [ ] **Step 5: Run full E2E**

Run:

```bash
cd apps/web
npm run e2e
```

Expected: all Playwright tests pass on `chromium-mobile` and `chromium-desktop`.

- [ ] **Step 6: Manually verify the three mobile sizes**

Run the dev server:

```bash
cd apps/web
NEXT_PUBLIC_BFF_BASE_URL=http://127.0.0.1:4999 npm run dev
```

Open `http://localhost:3000` and check these viewports in Chrome DevTools:

```text
375x667
390x844
430x932
```

Expected:
- `/` first visit shows a branded loading state briefly, then redirects to `/onboarding`.
- `/onboarding` dot buttons move slides without exposing invisible controls through Tab.
- Browser zoom is not blocked on a real mobile browser or mobile emulator.
- `/ads`, `/settings`, and `/generate/chat/complete` have no horizontal overflow and feel less cramped on 390x844.

- [ ] **Step 7: Commit any verification-only README correction**

Only run this if the manual verification reveals a docs wording mismatch:

```bash
git add apps/web/README.md
git commit -m "docs(web): clarify QA verification steps"
```

---

## Self-Review

**Spec coverage:**  
The plan covers all QA priorities from the latest review:
- Onboarding hidden focus: Task 1.
- Mobile zoom accessibility: Task 2.
- First-entry blank state: Task 3.
- Dense mobile scroll screens: Task 4.
- Stale Playwright server reuse: Task 5.
- Full lint, unit, build, E2E, and manual viewport checks: Task 6.

**Placeholder scan:**  
No step relies on `TBD`, `TODO`, vague "add tests", or unspecified files. Each code-changing task includes exact file paths, concrete code, exact commands, and expected outcomes.

**Type consistency:**  
The plan uses existing names from the codebase:
- `OnboardingStep`
- `buildDashboardHref`
- `buildBrandKitHref`
- `ONBOARDING_COMPLETED_STORAGE_KEY`
- `ONBOARDING_COMPLETED_VALUE`
- `MobileShell`
- CSS module import name `styles`

No new route contract is introduced.
