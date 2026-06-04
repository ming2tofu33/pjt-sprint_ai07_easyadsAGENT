# Chat Start UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js `apps/web` frontend MVP for scenario C, "대화로 시작하기", matching the provided mobile-first visual flow and using mock state until BFF/orchestrator APIs are ready.

**Architecture:** Create a new Next.js App Router app at `apps/web`. Keep the first implementation frontend-only with a typed client-side state machine that mirrors `chat_start` MarketingState concepts, then isolate visual shell/components so API wiring can replace the mock flow later without rewriting screens.

**Tech Stack:** Next.js 14, React 18, TypeScript, CSS Modules/global CSS variables, lucide-react icons, Vitest, React Testing Library, Playwright.

---

## Scope

Build only scenario C:

- Step 1: 대화로 시작하기
- Step 2: AI가 의도를 파악하고 질문해요
- Step 3: 문구와 채널을 선택해요
- Step 4: 브리프를 확인하고 생성해요

Do not build scenario A, scenario B, real image generation, login, storage, pricing, or BFF API calls in this plan. The UI should run locally and preserve state while the page is open.

## Source Context

- Scenario text source: `/home/spai0710/pjt-sprint_ai07_easyadsAGENT/images/시나리오 핵심 내용.md`
- Scenario C image source: `/home/spai0710/pjt-sprint_ai07_easyadsAGENT/images/개떡찰떡C.png`
- Target worktree: `/home/spai0710/pjt-sprint_ai07_easyadsAGENT/.worktrees/feat-fe-dm-ui`
- Target branch: `feat/fe/dm-ui`
- Monorepo target: `apps/web`
- Backend schema references:
  - `orchestrator/app/schemas/llm_marketing.py`
  - `orchestrator/app/graph/state.py`

## File Structure

Create these files:

- `apps/web/package.json` - frontend app scripts and dependencies.
- `apps/web/next.config.mjs` - Next.js config.
- `apps/web/tsconfig.json` - TypeScript config for the web app.
- `apps/web/.eslintrc.json` - Next.js lint config.
- `apps/web/vitest.config.ts` - unit/component test config.
- `apps/web/playwright.config.ts` - browser smoke test config.
- `apps/web/app/layout.tsx` - global HTML shell and metadata.
- `apps/web/app/page.tsx` - redirect-style landing entry to chat UI.
- `apps/web/app/generate/chat/page.tsx` - server page wrapper.
- `apps/web/app/generate/chat/ChatGenerateClient.tsx` - client state owner and step router.
- `apps/web/app/globals.css` - reset, CSS variables, app background.
- `apps/web/components/generate/MobileShell.tsx` - centered mobile device shell.
- `apps/web/components/generate/StepHeader.tsx` - consistent top title and progress strip.
- `apps/web/components/generate/ChatStartStep.tsx` - scenario C step 1.
- `apps/web/components/generate/IntentReviewStep.tsx` - scenario C step 2.
- `apps/web/components/generate/CopyChannelStep.tsx` - scenario C step 3.
- `apps/web/components/generate/BriefConfirmStep.tsx` - scenario C step 4.
- `apps/web/components/generate/ChoiceChip.tsx` - reusable selectable chip/button.
- `apps/web/components/generate/BriefRow.tsx` - icon + label + value summary row.
- `apps/web/components/generate/generate.module.css` - component-specific UI styling.
- `apps/web/lib/chat-flow.ts` - typed state, reducer actions, mock inference, brief builder.
- `apps/web/lib/chat-flow.test.ts` - state machine unit tests.
- `apps/web/types/marketing.ts` - frontend mirror types for scenario C.
- `apps/web/app/generate/chat/ChatGenerateClient.test.tsx` - component flow test.
- `apps/web/e2e/chat-start.spec.ts` - Playwright route and responsive smoke tests.
- `apps/web/public/scenarios/gaetteok-chat-c.png` - copied scenario C reference image.
- `apps/web/public/scenarios/scenario-summary.md` - copied scenario summary markdown.

Modify these files:

- `.gitignore` - add frontend build/cache ignores if missing.
- `README.md` - add short web app setup and run commands.

## Design Rules

Use these exact visual foundations:

- Page background: `#f8f8f4`
- Text: `#111111`
- Muted text: `#73736f`
- Border: `#e8e6df`
- Lime accent: `#eaff79`
- Soft lime: `#f3ffd0`
- Purple accent: `#aa92ff`
- Soft purple: `#f3efff`
- Coral accent: `#ffb3a7`
- Soft coral: `#fff0ea`
- Main CTA: black background, white text
- Radius: cards `18px`, chips `999px`, mobile shell `34px`
- Button height: primary CTA `56px`, chip minimum `44px`
- The UI must be mobile-first. Desktop centers a phone-width surface, not a dashboard.

Use lucide-react icons for UI controls:

- `Send`
- `Image`
- `MessageCircle`
- `Search`
- `Heart`
- `Megaphone`
- `Gift`
- `Coffee`
- `Utensils`
- `Sparkles`
- `ChevronLeft`
- `Check`
- `PenLine`
- `Star`

## Task 1: Bring Scenario Assets Into The Worktree

**Files:**
- Create: `apps/web/public/scenarios/gaetteok-chat-c.png`
- Create: `apps/web/public/scenarios/scenario-summary.md`

- [ ] **Step 1: Create the scenario asset directory**

Run:

```bash
mkdir -p apps/web/public/scenarios
```

Expected: command exits with code `0`.

- [ ] **Step 2: Copy the scenario C image and markdown into the worktree**

Run:

```bash
cp /home/spai0710/pjt-sprint_ai07_easyadsAGENT/images/개떡찰떡C.png apps/web/public/scenarios/gaetteok-chat-c.png
cp /home/spai0710/pjt-sprint_ai07_easyadsAGENT/images/시나리오\ 핵심\ 내용.md apps/web/public/scenarios/scenario-summary.md
```

Expected: both files exist under `apps/web/public/scenarios`.

- [ ] **Step 3: Verify copied files**

Run:

```bash
find apps/web/public/scenarios -maxdepth 1 -type f -print | sort
```

Expected output includes:

```text
apps/web/public/scenarios/gaetteok-chat-c.png
apps/web/public/scenarios/scenario-summary.md
```

- [ ] **Step 4: Commit scenario assets**

Run:

```bash
git add apps/web/public/scenarios
git commit -m "chore(fe): add chat scenario reference assets"
```

Expected: commit succeeds.

## Task 2: Scaffold The Next.js Web App

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.mjs`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/.eslintrc.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/app/globals.css`
- Modify: `.gitignore`

- [ ] **Step 1: Write `apps/web/package.json`**

Create `apps/web/package.json`:

```json
{
  "name": "@easyads/web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev --hostname 0.0.0.0 --port 3000",
    "build": "next build",
    "start": "next start --hostname 0.0.0.0 --port 3000",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  },
  "dependencies": {
    "clsx": "2.1.1",
    "lucide-react": "0.468.0",
    "next": "14.2.18",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@playwright/test": "1.49.0",
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.0.1",
    "@types/node": "20.17.6",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "eslint": "8.57.1",
    "eslint-config-next": "14.2.18",
    "jsdom": "25.0.1",
    "typescript": "5.6.3",
    "vitest": "2.1.5"
  }
}
```

- [ ] **Step 2: Write Next, TypeScript, ESLint, Vitest, and Playwright config**

Create `apps/web/next.config.mjs`:

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true
};

export default nextConfig;
```

Create `apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Create `apps/web/.eslintrc.json`:

```json
{
  "extends": ["next/core-web-vitals"]
}
```

Create `apps/web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: []
  },
  resolve: {
    alias: {
      "@": new URL(".", import.meta.url).pathname
    }
  }
});
```

Create `apps/web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry"
  },
  projects: [
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } }
  ]
});
```

- [ ] **Step 3: Create the App Router shell**

Create `apps/web/app/layout.tsx`:

```tsx
import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "개떡찰떡",
  description: "대충 말해도 AI가 광고 브리프를 완성하는 이미지 광고 앱"
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#f8f8f4"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
```

Create `apps/web/app/page.tsx`:

```tsx
import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/generate/chat");
}
```

Create `apps/web/app/globals.css`:

```css
:root {
  --color-page: #f8f8f4;
  --color-surface: #ffffff;
  --color-text: #111111;
  --color-muted: #73736f;
  --color-border: #e8e6df;
  --color-lime: #eaff79;
  --color-lime-soft: #f3ffd0;
  --color-purple: #aa92ff;
  --color-purple-soft: #f3efff;
  --color-coral: #ffb3a7;
  --color-coral-soft: #fff0ea;
  --shadow-phone: 0 24px 80px rgba(17, 17, 17, 0.13);
  --shadow-card: 0 10px 30px rgba(17, 17, 17, 0.07);
}

* {
  box-sizing: border-box;
}

html,
body {
  min-height: 100%;
  margin: 0;
}

body {
  background:
    radial-gradient(circle at 22% 8%, rgba(234, 255, 121, 0.32), transparent 28rem),
    radial-gradient(circle at 86% 18%, rgba(170, 146, 255, 0.22), transparent 24rem),
    var(--color-page);
  color: var(--color-text);
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
}

button,
input,
textarea {
  font: inherit;
}

button {
  cursor: pointer;
}

a {
  color: inherit;
  text-decoration: none;
}
```

- [ ] **Step 4: Update `.gitignore` for frontend build outputs**

Append these lines if they are not already present:

```gitignore
node_modules/
.next/
playwright-report/
test-results/
```

- [ ] **Step 5: Install dependencies**

Run:

```bash
cd apps/web
npm install
```

Expected: `package-lock.json` is created and dependency installation completes.

- [ ] **Step 6: Verify the scaffold builds**

Run:

```bash
cd apps/web
npm run lint
npm run build
```

Expected: `npm run lint` and `npm run build` both exit with code `0`.

- [ ] **Step 7: Commit scaffold**

Run:

```bash
git add .gitignore apps/web
git commit -m "feat(fe): scaffold Next.js web app"
```

Expected: commit succeeds.

## Task 3: Define Chat Flow Types And State Machine

**Files:**
- Create: `apps/web/types/marketing.ts`
- Create: `apps/web/lib/chat-flow.ts`
- Create: `apps/web/lib/chat-flow.test.ts`

- [ ] **Step 1: Write failing tests for the chat flow**

Create `apps/web/lib/chat-flow.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  buildBrief,
  chatFlowReducer,
  createInitialChatFlowState,
  inferContextFromPrompt
} from "./chat-flow";

describe("chat flow state", () => {
  it("infers cafe strawberry latte launch context from a natural Korean prompt", () => {
    const context = inferContextFromPrompt("우리 카페 딸기라떼 신메뉴 광고 만들어줘");

    expect(context.businessType).toBe("카페");
    expect(context.itemOrService).toBe("딸기라떼");
    expect(context.promotionGoal).toBe("신메뉴 출시");
  });

  it("moves from start to intent review after prompt submit", () => {
    const state = createInitialChatFlowState();
    const next = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });

    expect(next.step).toBe(2);
    expect(next.userInput).toContain("딸기라떼");
    expect(next.progress.current).toBe(1);
    expect(next.progress.total).toBe(4);
  });

  it("builds a complete brief after tone copy and channel selections", () => {
    let state = createInitialChatFlowState();
    state = chatFlowReducer(state, {
      type: "submitPrompt",
      prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘"
    });
    state = chatFlowReducer(state, { type: "selectTone", tone: "감성적인" });
    state = chatFlowReducer(state, { type: "continueToCopy" });
    state = chatFlowReducer(state, {
      type: "selectCopy",
      copyId: "spring-strawberry"
    });
    state = chatFlowReducer(state, {
      type: "selectChannel",
      channelId: "instagram-feed"
    });
    state = chatFlowReducer(state, { type: "continueToBrief" });

    const brief = buildBrief(state);

    expect(state.step).toBe(4);
    expect(brief.purpose).toBe("신메뉴 출시");
    expect(brief.item).toBe("딸기라떼");
    expect(brief.copy).toBe("봄을 닮은 한 잔, 딸기라떼 출시");
    expect(brief.channel).toBe("인스타 피드 (1:1)");
    expect(brief.imageDirection).toContain("크림톤 배경");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd apps/web
npm run test -- lib/chat-flow.test.ts
```

Expected: FAIL because `./chat-flow` does not exist.

- [ ] **Step 3: Add frontend marketing types**

Create `apps/web/types/marketing.ts`:

```ts
export type ChatFlowStep = 1 | 2 | 3 | 4;

export type EntryMode = "chat_start";

export type ProgressState = {
  current: number;
  total: number;
  label: string;
};

export type InferredContext = {
  businessType: string;
  itemOrService: string;
  promotionGoal: string;
};

export type ToneOption = {
  id: string;
  label: string;
  icon: "heart" | "leaf" | "diamond" | "smile" | "sparkles" | "star";
};

export type CopyOption = {
  id: string;
  headline: string;
  selectedByDefault?: boolean;
};

export type ChannelOption = {
  id: string;
  label: string;
  ratio: string;
};

export type ChatBrief = {
  purpose: string;
  item: string;
  copy: string;
  tone: string;
  channel: string;
  imageDirection: string;
};

export type ChatFlowState = {
  entryMode: EntryMode;
  step: ChatFlowStep;
  progress: ProgressState;
  userInput: string;
  inferredContext: InferredContext;
  selectedTone: string;
  selectedCopyId: string;
  selectedChannelId: string;
  customDirection: string;
};

export type ChatFlowAction =
  | { type: "submitPrompt"; prompt: string }
  | { type: "selectTone"; tone: string }
  | { type: "continueToCopy" }
  | { type: "selectCopy"; copyId: string }
  | { type: "selectChannel"; channelId: string }
  | { type: "setCustomDirection"; value: string }
  | { type: "continueToBrief" }
  | { type: "back" };
```

- [ ] **Step 4: Add the state machine implementation**

Create `apps/web/lib/chat-flow.ts`:

```ts
import type {
  ChannelOption,
  ChatBrief,
  ChatFlowAction,
  ChatFlowState,
  CopyOption,
  InferredContext,
  ToneOption
} from "@/types/marketing";

export const toneOptions: ToneOption[] = [
  { id: "emotional", label: "감성적인", icon: "heart" },
  { id: "fresh", label: "상큼한", icon: "leaf" },
  { id: "premium", label: "고급스러운", icon: "diamond" },
  { id: "cute", label: "귀여운", icon: "smile" },
  { id: "clean", label: "깔끔한", icon: "sparkles" },
  { id: "bold", label: "강렬한", icon: "star" }
];

export const copyOptions: CopyOption[] = [
  { id: "spring-strawberry", headline: "봄을 닮은 한 잔, 딸기라떼 출시", selectedByDefault: true },
  { id: "today-sweet", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" },
  { id: "full-strawberry", headline: "딸기 한가득, 지금 가장 상큼한 메뉴" }
];

export const channelOptions: ChannelOption[] = [
  { id: "instagram-feed", label: "인스타 피드", ratio: "1:1" },
  { id: "instagram-story", label: "인스타 스토리", ratio: "9:16" },
  { id: "poster", label: "포스터", ratio: "4:5" },
  { id: "flyer", label: "전단지", ratio: "A4" }
];

export function inferContextFromPrompt(prompt: string): InferredContext {
  const normalized = prompt.replace(/\s+/g, "");
  const businessType = normalized.includes("카페") ? "카페" : "카페";
  const itemOrService = normalized.includes("딸기라떼") ? "딸기라떼" : "대표 메뉴";
  const promotionGoal = normalized.includes("신메뉴") ? "신메뉴 출시" : "광고 홍보";

  return {
    businessType,
    itemOrService,
    promotionGoal
  };
}

export function createInitialChatFlowState(): ChatFlowState {
  return {
    entryMode: "chat_start",
    step: 1,
    progress: { current: 0, total: 4, label: "대화 시작" },
    userInput: "",
    inferredContext: {
      businessType: "",
      itemOrService: "",
      promotionGoal: ""
    },
    selectedTone: "감성적인",
    selectedCopyId: "spring-strawberry",
    selectedChannelId: "instagram-feed",
    customDirection: ""
  };
}

export function chatFlowReducer(state: ChatFlowState, action: ChatFlowAction): ChatFlowState {
  switch (action.type) {
    case "submitPrompt":
      return {
        ...state,
        step: 2,
        progress: { current: 1, total: 4, label: "정보 입력" },
        userInput: action.prompt,
        inferredContext: inferContextFromPrompt(action.prompt)
      };
    case "selectTone":
      return {
        ...state,
        selectedTone: action.tone
      };
    case "continueToCopy":
      return {
        ...state,
        step: 3,
        progress: { current: 3, total: 4, label: "정보 입력" }
      };
    case "selectCopy":
      return {
        ...state,
        selectedCopyId: action.copyId
      };
    case "selectChannel":
      return {
        ...state,
        selectedChannelId: action.channelId
      };
    case "setCustomDirection":
      return {
        ...state,
        customDirection: action.value
      };
    case "continueToBrief":
      return {
        ...state,
        step: 4,
        progress: { current: 4, total: 4, label: "정보 입력" }
      };
    case "back":
      return {
        ...state,
        step: Math.max(1, state.step - 1) as ChatFlowState["step"]
      };
    default:
      return state;
  }
}

export function selectedCopyLabel(state: ChatFlowState): string {
  return copyOptions.find((copy) => copy.id === state.selectedCopyId)?.headline ?? copyOptions[0].headline;
}

export function selectedChannelLabel(state: ChatFlowState): string {
  const channel = channelOptions.find((item) => item.id === state.selectedChannelId) ?? channelOptions[0];
  return `${channel.label} (${channel.ratio})`;
}

export function buildBrief(state: ChatFlowState): ChatBrief {
  return {
    purpose: state.inferredContext.promotionGoal,
    item: state.inferredContext.itemOrService,
    copy: selectedCopyLabel(state),
    tone: `${state.selectedTone}이고 상큼한 카페 무드`,
    channel: selectedChannelLabel(state),
    imageDirection:
      state.customDirection ||
      "크림톤 배경, 딸기라떼를 중앙에 크게 배치하고 우측 여백에 카피 배치"
  };
}
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd apps/web
npm run test -- lib/chat-flow.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit state machine**

Run:

```bash
git add apps/web/types apps/web/lib
git commit -m "feat(fe): add chat generation flow state"
```

Expected: commit succeeds.

## Task 4: Build Shared Mobile UI Components

**Files:**
- Create: `apps/web/components/generate/generate.module.css`
- Create: `apps/web/components/generate/MobileShell.tsx`
- Create: `apps/web/components/generate/StepHeader.tsx`
- Create: `apps/web/components/generate/ChoiceChip.tsx`
- Create: `apps/web/components/generate/BriefRow.tsx`

- [ ] **Step 1: Create shared component CSS**

Create `apps/web/components/generate/generate.module.css` with these class groups:

```css
.page {
  min-height: 100dvh;
  padding: 32px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.phone {
  width: min(100%, 390px);
  min-height: 760px;
  background: var(--color-surface);
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 34px;
  box-shadow: var(--shadow-phone);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.statusBar {
  height: 42px;
  padding: 14px 22px 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 800;
}

.signal {
  display: flex;
  gap: 4px;
  align-items: center;
}

.body {
  flex: 1;
  padding: 0 18px 22px;
  display: flex;
  flex-direction: column;
}

.topNav {
  min-height: 44px;
  display: grid;
  grid-template-columns: 40px 1fr 40px;
  align-items: center;
}

.iconButton {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.title {
  margin: 0;
  text-align: center;
  font-size: 17px;
  line-height: 1.25;
  font-weight: 900;
  letter-spacing: 0;
}

.hero {
  margin-top: 14px;
  padding: 28px 22px;
  border-radius: 22px;
  background: linear-gradient(145deg, var(--color-lime-soft), var(--color-lime));
  text-align: center;
  border: 1px solid rgba(176, 203, 32, 0.38);
}

.sectionTitle {
  margin: 22px 0 10px;
  font-size: 13px;
  font-weight: 900;
}

.muted {
  color: var(--color-muted);
}

.chipGrid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.chip {
  min-height: 48px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #fff;
  color: var(--color-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 10px;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}

.chipSelected {
  border-color: var(--color-purple);
  background: var(--color-purple-soft);
  color: #5f43d6;
}

.inputCard {
  margin-top: auto;
  border: 1px solid var(--color-purple);
  border-radius: 18px;
  padding: 12px;
  background: #fff;
  display: grid;
  grid-template-columns: 32px 1fr 42px;
  align-items: center;
  gap: 8px;
}

.input {
  border: 0;
  outline: 0;
  min-width: 0;
  color: var(--color-text);
}

.sendButton {
  width: 42px;
  height: 42px;
  border-radius: 999px;
  border: 0;
  background: #050505;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.primaryButton {
  width: 100%;
  min-height: 56px;
  border: 0;
  border-radius: 14px;
  background: #050505;
  color: #fff;
  font-weight: 900;
  font-size: 16px;
}

.progressWrap {
  margin-top: 18px;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 800;
}

.progressTrack {
  height: 4px;
  border-radius: 999px;
  background: #ebe9e4;
  overflow: hidden;
}

.progressBar {
  height: 100%;
  border-radius: inherit;
  background: var(--color-purple);
}

.card {
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow-card);
}

@media (max-width: 430px) {
  .page {
    padding: 0;
    align-items: stretch;
  }

  .phone {
    width: 100%;
    min-height: 100dvh;
    border-radius: 0;
    border: 0;
    box-shadow: none;
  }
}
```

- [ ] **Step 2: Create `MobileShell`**

Create `apps/web/components/generate/MobileShell.tsx`:

```tsx
import styles from "./generate.module.css";

export function MobileShell({ children }: { children: React.ReactNode }) {
  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="개떡찰떡 모바일 화면">
        <div className={styles.statusBar} aria-hidden="true">
          <span>9:41</span>
          <span className={styles.signal}>● ● ●</span>
        </div>
        <div className={styles.body}>{children}</div>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Create `StepHeader`**

Create `apps/web/components/generate/StepHeader.tsx`:

```tsx
import { ChevronLeft } from "lucide-react";
import styles from "./generate.module.css";

type StepHeaderProps = {
  title: string;
  canGoBack?: boolean;
  onBack?: () => void;
};

export function StepHeader({ title, canGoBack = false, onBack }: StepHeaderProps) {
  return (
    <header className={styles.topNav}>
      {canGoBack ? (
        <button className={styles.iconButton} type="button" aria-label="이전 단계" onClick={onBack}>
          <ChevronLeft size={22} strokeWidth={2.4} />
        </button>
      ) : (
        <span />
      )}
      <h1 className={styles.title}>{title}</h1>
      <span />
    </header>
  );
}
```

- [ ] **Step 4: Create `ChoiceChip`**

Create `apps/web/components/generate/ChoiceChip.tsx`:

```tsx
import clsx from "clsx";
import styles from "./generate.module.css";

type ChoiceChipProps = {
  selected?: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  ariaLabel?: string;
};

export function ChoiceChip({ selected = false, children, onClick, ariaLabel }: ChoiceChipProps) {
  return (
    <button
      type="button"
      className={clsx(styles.chip, selected && styles.chipSelected)}
      aria-pressed={selected}
      aria-label={ariaLabel}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 5: Create `BriefRow`**

Create `apps/web/components/generate/BriefRow.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";

type BriefRowProps = {
  icon: LucideIcon;
  label: string;
  value: string;
};

export function BriefRow({ icon: Icon, label, value }: BriefRowProps) {
  return (
    <div className="brief-row">
      <Icon size={17} strokeWidth={2.3} aria-hidden="true" />
      <span className="brief-row-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

- [ ] **Step 6: Add required brief row CSS to `generate.module.css`**

Append:

```css
.briefRow {
  display: grid;
  grid-template-columns: 22px 88px 1fr;
  gap: 8px;
  align-items: start;
  padding: 12px 0;
  border-bottom: 1px solid rgba(17, 17, 17, 0.08);
  font-size: 13px;
}
```

Then update `BriefRow.tsx` to use CSS modules:

```tsx
import type { LucideIcon } from "lucide-react";
import styles from "./generate.module.css";

type BriefRowProps = {
  icon: LucideIcon;
  label: string;
  value: string;
};

export function BriefRow({ icon: Icon, label, value }: BriefRowProps) {
  return (
    <div className={styles.briefRow}>
      <Icon size={17} strokeWidth={2.3} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

- [ ] **Step 7: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 8: Commit shared UI**

Run:

```bash
git add apps/web/components/generate
git commit -m "feat(fe): add mobile generation UI primitives"
```

Expected: commit succeeds.

## Task 5: Build Step 1, Chat Start

**Files:**
- Create: `apps/web/components/generate/ChatStartStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add CSS for step 1 lists**

Append to `generate.module.css`:

```css
.exampleList {
  display: grid;
  gap: 9px;
}

.examplePill {
  min-height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: #fff;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text);
  font-size: 12px;
  font-weight: 750;
}

.heroIcon {
  width: 48px;
  height: 48px;
  margin: 0 auto 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.heroTitle {
  margin: 0;
  font-size: 17px;
  font-weight: 900;
}

.heroCopy {
  margin: 12px 0 0;
  color: #4f552c;
  font-size: 13px;
  line-height: 1.55;
  font-weight: 700;
}

.helperText {
  margin: 12px 0 0;
  text-align: center;
  color: #7e67d8;
  font-size: 12px;
  font-weight: 800;
}
```

- [ ] **Step 2: Create the component**

Create `apps/web/components/generate/ChatStartStep.tsx`:

```tsx
"use client";

import { Coffee, Gift, Image, Megaphone, MessageCircle, Send, Utensils } from "lucide-react";
import { useState } from "react";
import { ChoiceChip } from "./ChoiceChip";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

const examples = [
  "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
  "삼겹살집 회식 손님 많이 오게 포스터 만들어줘",
  "네일샵 여름 이벤트 인스타 스토리 만들어줘"
];

const quickStarts = [
  { label: "카페 신메뉴", icon: Coffee },
  { label: "음식점 할인", icon: Utensils },
  { label: "뷰티 예약", icon: Gift },
  { label: "리뷰 이벤트", icon: MessageCircle },
  { label: "오픈 홍보", icon: Megaphone }
];

type ChatStartStepProps = {
  onSubmit: (prompt: string) => void;
};

export function ChatStartStep({ onSubmit }: ChatStartStepProps) {
  const [value, setValue] = useState("우리 카페 딸기라떼 신메뉴 광고 만들어줘");

  function submitPrompt() {
    const prompt = value.trim();
    if (prompt.length > 0) {
      onSubmit(prompt);
    }
  }

  return (
    <>
      <StepHeader title="대화로 찰떡 만들기" />
      <section className={styles.hero}>
        <span className={styles.heroIcon}>
          <MessageCircle size={25} strokeWidth={2.4} />
        </span>
        <h2 className={styles.heroTitle}>원하는 광고를 편하게 적어보세요.</h2>
        <p className={styles.heroCopy}>AI가 부족한 정보를 물어보며 광고 브리프를 완성해드려요.</p>
      </section>

      <h2 className={styles.sectionTitle}>예시로 시작해보기</h2>
      <div className={styles.exampleList}>
        {examples.map((example) => (
          <button className={styles.examplePill} key={example} type="button" onClick={() => setValue(example)}>
            <Gift size={15} aria-hidden="true" />
            <span>{example}</span>
          </button>
        ))}
      </div>

      <h2 className={styles.sectionTitle}>빠른 시작</h2>
      <div className={styles.chipGrid}>
        {quickStarts.map(({ label, icon: Icon }) => (
          <ChoiceChip key={label} onClick={() => setValue(`${label} 광고 만들어줘`)}>
            <Icon size={16} aria-hidden="true" />
            <span>{label}</span>
          </ChoiceChip>
        ))}
      </div>

      <label className={styles.inputCard}>
        <Image size={19} aria-hidden="true" />
        <input
          className={styles.input}
          value={value}
          aria-label="광고 요청 입력"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              submitPrompt();
            }
          }}
        />
        <button className={styles.sendButton} type="button" aria-label="요청 보내기" onClick={submitPrompt}>
          <Send size={18} aria-hidden="true" />
        </button>
      </label>
      <p className={styles.helperText}>대충 써도 괜찮아요. AI가 찰떡같이 알아들을게요.</p>
    </>
  );
}
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit step 1**

Run:

```bash
git add apps/web/components/generate
git commit -m "feat(fe): build chat start step"
```

Expected: commit succeeds.

## Task 6: Build Step 2, Intent Review

**Files:**
- Create: `apps/web/components/generate/IntentReviewStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add CSS for assistant bubbles and context card**

Append to `generate.module.css`:

```css
.assistantBubble {
  margin-top: 18px;
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  align-items: start;
}

.assistantAvatar {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: var(--color-purple);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
}

.bubble {
  border-radius: 16px;
  background: #f3f2f0;
  padding: 13px 14px;
  font-size: 13px;
  line-height: 1.5;
  font-weight: 750;
}

.contextCard {
  margin-top: 16px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #d9cffd;
  background: linear-gradient(160deg, #fbfaff, var(--color-purple-soft));
}

.contextTitle {
  margin: 0 0 14px;
  color: #6d52d8;
  font-size: 13px;
  font-weight: 900;
}

.contextGrid {
  display: grid;
  gap: 12px;
}

.contextItem {
  display: grid;
  grid-template-columns: 82px 1fr;
  gap: 10px;
  font-size: 13px;
}

.contextItem span {
  color: #5f5582;
  font-weight: 800;
}

.contextItem strong {
  font-weight: 900;
}
```

- [ ] **Step 2: Create the component**

Create `apps/web/components/generate/IntentReviewStep.tsx`:

```tsx
"use client";

import { Diamond, Heart, Leaf, Smile, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { toneOptions } from "@/lib/chat-flow";
import { ChoiceChip } from "./ChoiceChip";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

const toneIconMap = {
  heart: Heart,
  leaf: Leaf,
  diamond: Diamond,
  smile: Smile,
  sparkles: Sparkles,
  star: Star
};

type IntentReviewStepProps = {
  state: ChatFlowState;
  onSelectTone: (tone: string) => void;
  onContinue: () => void;
  onBack: () => void;
};

export function IntentReviewStep({ state, onSelectTone, onContinue, onBack }: IntentReviewStepProps) {
  return (
    <>
      <StepHeader title="AI가 이렇게 이해했어요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>좋아요! 내용을 이해했어요. 제가 파악한 내용은 아래와 같아요.</p>
      </div>

      <section className={styles.contextCard} aria-label="AI가 파악한 내용">
        <h2 className={styles.contextTitle}>파악한 내용</h2>
        <div className={styles.contextGrid}>
          <div className={styles.contextItem}>
            <span>업종</span>
            <strong>{state.inferredContext.businessType}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>상품/서비스</span>
            <strong>{state.inferredContext.itemOrService}</strong>
          </div>
          <div className={styles.contextItem}>
            <span>광고 목적</span>
            <strong>{state.inferredContext.promotionGoal}</strong>
          </div>
        </div>
      </section>

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>더 잘 맞는 광고를 만들기 위해 아래 정보를 조금만 알려주세요.</p>
      </div>

      <h2 className={styles.sectionTitle}>어떤 분위기의 광고가 좋을까요?</h2>
      <div className={styles.chipGrid}>
        {toneOptions.map((tone) => {
          const Icon = toneIconMap[tone.icon];
          return (
            <ChoiceChip
              key={tone.id}
              selected={state.selectedTone === tone.label}
              onClick={() => onSelectTone(tone.label)}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{tone.label}</span>
            </ChoiceChip>
          );
        })}
      </div>

      <div className={styles.progressWrap}>
        <span>정보 입력 {state.progress.current}/{state.progress.total}</span>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: "25%" }} />
        </span>
      </div>

      <button className={styles.primaryButton} type="button" onClick={onContinue}>
        문구 고르기
      </button>
    </>
  );
}
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit step 2**

Run:

```bash
git add apps/web/components/generate
git commit -m "feat(fe): build intent review step"
```

Expected: commit succeeds.

## Task 7: Build Step 3, Copy And Channel Selection

**Files:**
- Create: `apps/web/components/generate/CopyChannelStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add CSS for selectable copy and channel cards**

Append to `generate.module.css`:

```css
.selectList {
  display: grid;
  gap: 10px;
}

.copyCard {
  min-height: 58px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #fff;
  padding: 13px 14px;
  display: grid;
  grid-template-columns: 26px 1fr 24px;
  gap: 10px;
  align-items: center;
  text-align: left;
  font-weight: 900;
}

.copyCardSelected {
  border-color: var(--color-purple);
  background: var(--color-purple-soft);
}

.copyNumber {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #111;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
}

.channelGrid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}

.channelCard {
  min-height: 84px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #fff;
  padding: 10px 6px;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 850;
}

.channelCardSelected {
  border-color: var(--color-purple);
  background: var(--color-purple-soft);
  color: #6147d3;
}

.textareaCard {
  margin-top: 14px;
  min-height: 50px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #fff;
  padding: 12px;
  display: grid;
  grid-template-columns: 1fr 24px;
  gap: 8px;
}

.textarea {
  border: 0;
  outline: 0;
  resize: none;
  min-width: 0;
  min-height: 24px;
  color: var(--color-text);
}
```

- [ ] **Step 2: Create the component**

Create `apps/web/components/generate/CopyChannelStep.tsx`:

```tsx
"use client";

import clsx from "clsx";
import { Check, Instagram, PenLine } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { channelOptions, copyOptions } from "@/lib/chat-flow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type CopyChannelStepProps = {
  state: ChatFlowState;
  onSelectCopy: (copyId: string) => void;
  onSelectChannel: (channelId: string) => void;
  onCustomDirection: (value: string) => void;
  onContinue: () => void;
  onBack: () => void;
};

export function CopyChannelStep({
  state,
  onSelectCopy,
  onSelectChannel,
  onCustomDirection,
  onContinue,
  onBack
}: CopyChannelStepProps) {
  return (
    <>
      <StepHeader title="문구와 채널을 골라주세요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>분위기까지 좋습니다! 이제 어울리는 문구와 사용할 채널을 선택해볼까요?</p>
      </div>

      <h2 className={styles.sectionTitle}>추천 문구</h2>
      <div className={styles.selectList}>
        {copyOptions.map((copy, index) => {
          const selected = state.selectedCopyId === copy.id;
          return (
            <button
              key={copy.id}
              type="button"
              className={clsx(styles.copyCard, selected && styles.copyCardSelected)}
              aria-pressed={selected}
              onClick={() => onSelectCopy(copy.id)}
            >
              <span className={styles.copyNumber}>{index + 1}</span>
              <span>{copy.headline}</span>
              {selected ? <Check size={19} aria-hidden="true" /> : <span />}
            </button>
          );
        })}
      </div>

      <h2 className={styles.sectionTitle}>어디에 사용할까요?</h2>
      <div className={styles.channelGrid}>
        {channelOptions.map((channel) => {
          const selected = state.selectedChannelId === channel.id;
          return (
            <button
              key={channel.id}
              type="button"
              className={clsx(styles.channelCard, selected && styles.channelCardSelected)}
              aria-pressed={selected}
              onClick={() => onSelectChannel(channel.id)}
            >
              <span>{channel.label}</span>
              <small>{channel.ratio}</small>
              <Instagram size={16} aria-hidden="true" />
            </button>
          );
        })}
      </div>

      <h2 className={styles.sectionTitle}>직접 입력하기</h2>
      <label className={styles.textareaCard}>
        <textarea
          className={styles.textarea}
          value={state.customDirection}
          aria-label="원하는 문구나 이미지 방향 직접 입력"
          placeholder="원하는 문구나 내용이 있다면 입력해보세요."
          onChange={(event) => onCustomDirection(event.target.value)}
        />
        <PenLine size={18} aria-hidden="true" />
      </label>

      <div className={styles.progressWrap}>
        <span>정보 입력 {state.progress.current}/{state.progress.total}</span>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: "75%" }} />
        </span>
      </div>

      <button className={styles.primaryButton} type="button" onClick={onContinue}>
        브리프 확인하기
      </button>
    </>
  );
}
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit step 3**

Run:

```bash
git add apps/web/components/generate
git commit -m "feat(fe): build copy and channel selection step"
```

Expected: commit succeeds.

## Task 8: Build Step 4, Brief Confirmation

**Files:**
- Create: `apps/web/components/generate/BriefConfirmStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Add CSS for final brief**

Append to `generate.module.css`:

```css
.briefCard {
  margin-top: 16px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(255, 179, 167, 0.8);
  background: linear-gradient(160deg, #fffaf7, var(--color-coral-soft));
}

.briefTitle {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 950;
}

.imageGuide {
  margin-top: 14px;
  border-radius: 16px;
  border: 1px solid rgba(255, 179, 167, 0.8);
  background: #fff8ed;
  padding: 14px;
  font-size: 13px;
  line-height: 1.55;
  font-weight: 800;
}

.completeNote {
  margin: 14px 0;
  border-radius: 16px;
  background: var(--color-coral-soft);
  padding: 15px;
  text-align: center;
  color: #6a4039;
  font-size: 13px;
  line-height: 1.5;
  font-weight: 850;
}

.finalProgress .progressBar {
  background: var(--color-coral);
}
```

- [ ] **Step 2: Create the component**

Create `apps/web/components/generate/BriefConfirmStep.tsx`:

```tsx
"use client";

import { Gift, Heart, Megaphone, Package, Sparkles, Star } from "lucide-react";
import type { ChatFlowState } from "@/types/marketing";
import { buildBrief } from "@/lib/chat-flow";
import { BriefRow } from "./BriefRow";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type BriefConfirmStepProps = {
  state: ChatFlowState;
  onBack: () => void;
};

export function BriefConfirmStep({ state, onBack }: BriefConfirmStepProps) {
  const brief = buildBrief(state);

  return (
    <>
      <StepHeader title="AI가 브리프를 정리했어요" canGoBack onBack={onBack} />

      <div className={styles.assistantBubble}>
        <span className={styles.assistantAvatar}>AI</span>
        <p className={styles.bubble}>모든 정보가 준비됐어요. 이 내용으로 광고를 만들 준비가 완료됐어요.</p>
      </div>

      <section className={styles.briefCard} aria-label="광고 브리프 요약">
        <h2 className={styles.briefTitle}>광고 브리프 요약</h2>
        <BriefRow icon={Megaphone} label="광고 목적" value={brief.purpose} />
        <BriefRow icon={Gift} label="상품/서비스" value={brief.item} />
        <BriefRow icon={Heart} label="선택한 문구" value={brief.copy} />
        <BriefRow icon={Star} label="분위기" value={brief.tone} />
        <BriefRow icon={Package} label="사용 채널" value={brief.channel} />
        <div className={styles.imageGuide}>
          <strong>추천 이미지 방향</strong>
          <p>{brief.imageDirection}</p>
        </div>
      </section>

      <p className={styles.completeNote}>이 내용으로 광고 이미지를 생성할게요. 마음에 들지 않으면 언제든 수정할 수 있어요.</p>

      <button className={styles.primaryButton} type="button">
        찰떡 광고 생성하기 <Sparkles size={18} aria-hidden="true" />
      </button>

      <div className={`${styles.progressWrap} ${styles.finalProgress}`}>
        <span>정보 입력 {state.progress.current}/{state.progress.total}</span>
        <span className={styles.progressTrack}>
          <span className={styles.progressBar} style={{ width: "100%" }} />
        </span>
      </div>
    </>
  );
}
```

- [ ] **Step 3: Run lint**

Run:

```bash
cd apps/web
npm run lint
```

Expected: PASS.

- [ ] **Step 4: Commit step 4**

Run:

```bash
git add apps/web/components/generate
git commit -m "feat(fe): build brief confirmation step"
```

Expected: commit succeeds.

## Task 9: Compose The Chat Page And Add Component Flow Test

**Files:**
- Create: `apps/web/app/generate/chat/page.tsx`
- Create: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Create: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Write failing component flow test**

Create `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatGenerateClient } from "./ChatGenerateClient";

describe("ChatGenerateClient", () => {
  it("walks through the four chat generation steps", () => {
    render(<ChatGenerateClient />);

    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy();
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("문구와 채널을 골라주세요")).toBeTruthy();
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy();
    expect(screen.getByText("인스타 스토리 (9:16)")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/web
npm run test -- app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: FAIL because `ChatGenerateClient` does not exist.

- [ ] **Step 3: Create page wrapper**

Create `apps/web/app/generate/chat/page.tsx`:

```tsx
import { ChatGenerateClient } from "./ChatGenerateClient";

export default function ChatGeneratePage() {
  return <ChatGenerateClient />;
}
```

- [ ] **Step 4: Create client flow router**

Create `apps/web/app/generate/chat/ChatGenerateClient.tsx`:

```tsx
"use client";

import { useReducer } from "react";
import { BriefConfirmStep } from "@/components/generate/BriefConfirmStep";
import { ChatStartStep } from "@/components/generate/ChatStartStep";
import { CopyChannelStep } from "@/components/generate/CopyChannelStep";
import { IntentReviewStep } from "@/components/generate/IntentReviewStep";
import { MobileShell } from "@/components/generate/MobileShell";
import { chatFlowReducer, createInitialChatFlowState } from "@/lib/chat-flow";

export function ChatGenerateClient() {
  const [state, dispatch] = useReducer(chatFlowReducer, undefined, createInitialChatFlowState);

  return (
    <MobileShell>
      {state.step === 1 ? (
        <ChatStartStep onSubmit={(prompt) => dispatch({ type: "submitPrompt", prompt })} />
      ) : null}

      {state.step === 2 ? (
        <IntentReviewStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectTone={(tone) => dispatch({ type: "selectTone", tone })}
          onContinue={() => dispatch({ type: "continueToCopy" })}
        />
      ) : null}

      {state.step === 3 ? (
        <CopyChannelStep
          state={state}
          onBack={() => dispatch({ type: "back" })}
          onSelectCopy={(copyId) => dispatch({ type: "selectCopy", copyId })}
          onSelectChannel={(channelId) => dispatch({ type: "selectChannel", channelId })}
          onCustomDirection={(value) => dispatch({ type: "setCustomDirection", value })}
          onContinue={() => dispatch({ type: "continueToBrief" })}
        />
      ) : null}

      {state.step === 4 ? <BriefConfirmStep state={state} onBack={() => dispatch({ type: "back" })} /> : null}
    </MobileShell>
  );
}
```

- [ ] **Step 5: Run component test**

Run:

```bash
cd apps/web
npm run test -- app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run all frontend tests**

Run:

```bash
cd apps/web
npm run test
```

Expected: PASS.

- [ ] **Step 7: Commit composed page**

Run:

```bash
git add apps/web/app/generate/chat
git commit -m "feat(fe): compose chat generation flow"
```

Expected: commit succeeds.

## Task 10: Add Browser Smoke Tests And Visual Verification

**Files:**
- Create: `apps/web/e2e/chat-start.spec.ts`

- [ ] **Step 1: Install Playwright browser**

Run:

```bash
cd apps/web
npx playwright install chromium
```

Expected: Chromium browser installation completes.

- [ ] **Step 2: Create Playwright smoke test**

Create `apps/web/e2e/chat-start.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("chat start flow reaches final brief on mobile", async ({ page }) => {
  await page.goto("/generate/chat");

  await expect(page.getByText("대화로 찰떡 만들기")).toBeVisible();
  await page.getByLabel("요청 보내기").click();

  await expect(page.getByText("AI가 이렇게 이해했어요")).toBeVisible();
  await page.getByRole("button", { name: /상큼한/ }).click();
  await page.getByRole("button", { name: "문구 고르기" }).click();

  await expect(page.getByText("문구와 채널을 골라주세요")).toBeVisible();
  await page.getByRole("button", { name: /인스타 스토리/ }).click();
  await page.getByRole("button", { name: "브리프 확인하기" }).click();

  await expect(page.getByText("AI가 브리프를 정리했어요")).toBeVisible();
  await expect(page.getByText("찰떡 광고 생성하기")).toBeVisible();
});

test("desktop keeps the app in a centered mobile shell", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/generate/chat");

  const shell = page.getByLabel("개떡찰떡 모바일 화면");
  await expect(shell).toBeVisible();

  const box = await shell.boundingBox();
  expect(box?.width).toBeLessThanOrEqual(392);
  expect(box?.height).toBeGreaterThan(700);
});
```

- [ ] **Step 3: Run e2e tests**

Run:

```bash
cd apps/web
npm run e2e
```

Expected: PASS for `chromium-mobile` and `chromium-desktop`.

- [ ] **Step 4: Create manual screenshots for review**

Run:

```bash
cd apps/web
npm run dev
```

Open `http://127.0.0.1:3000/generate/chat` and capture:

- Step 1 on mobile width `390x844`
- Step 2 on mobile width `390x844`
- Step 3 on mobile width `390x844`
- Step 4 on mobile width `390x844`
- Step 1 on desktop width `1440x960`

Expected:

- No overlapping text.
- The main CTA is visible on each step.
- The progress bar text does not wrap awkwardly.
- The phone shell is centered on desktop.
- The mobile viewport uses the full width with no outer phone border.

- [ ] **Step 5: Commit browser tests**

Run:

```bash
git add apps/web/e2e apps/web/playwright.config.ts
git commit -m "test(fe): add chat flow browser smoke tests"
```

Expected: commit succeeds.

## Task 11: Add README Web Commands

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add frontend setup section**

Append this section to `README.md`:

```markdown
## Web UI

The Next.js frontend lives in `apps/web`.

```bash
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000/generate/chat` for the scenario C chat-start UI.

Validation commands:

```bash
cd apps/web
npm run lint
npm run test
npm run build
npm run e2e
```
```

- [ ] **Step 2: Run final validation**

Run:

```bash
cd apps/web
npm run lint
npm run test
npm run build
npm run e2e
```

Expected: all commands exit with code `0`.

- [ ] **Step 3: Confirm backend baseline remains unchanged**

Run from the repository root:

```bash
/tmp/easyads-uv-bootstrap/bin/uv run python -m pytest orchestrator/tests
```

Expected: `182 passed` with existing Pillow deprecation warnings allowed.

- [ ] **Step 4: Commit documentation**

Run:

```bash
git add README.md
git commit -m "docs(fe): add web UI run commands"
```

Expected: commit succeeds.

## Final Acceptance Checklist

- [ ] `apps/web` exists and runs with `npm run dev`.
- [ ] `/generate/chat` starts at scenario C step 1.
- [ ] The flow can move from step 1 to step 4 with mouse/touch input.
- [ ] Step 1 includes example prompts, quick-start chips, input, and send button.
- [ ] Step 2 shows inferred context and tone chips.
- [ ] Step 3 shows copy candidates, channel cards, and direct input.
- [ ] Step 4 shows brief rows and recommended image direction.
- [ ] Desktop view centers a mobile app shell.
- [ ] Mobile view fills the viewport without desktop chrome.
- [ ] `npm run lint` passes.
- [ ] `npm run test` passes.
- [ ] `npm run build` passes.
- [ ] `npm run e2e` passes.
- [ ] `uv run python -m pytest orchestrator/tests` still passes.

## Self-Review Notes

- Spec coverage: The plan covers scenario C's four screens, visual language, mock MarketingState-like state, future API boundary, tests, and README instructions.
- Placeholder scan: The plan contains no unfinished markers and no unspecified implementation steps.
- Type consistency: `ChatFlowState`, `ChatFlowAction`, `ChatBrief`, copy/channel IDs, and reducer action names are defined before they are used by components and tests.
