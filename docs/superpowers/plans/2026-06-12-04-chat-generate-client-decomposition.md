# ChatGenerateClient Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce UI regression risk by moving storage helpers, non-chat surfaces, and route restoration logic out of `ChatGenerateClient.tsx`.

**Architecture:** Keep behavior unchanged while extracting one responsibility at a time. First move pure storage IO to a library, then split studio/reference/ads surfaces away from chat generation, then isolate route restoration into a hook. URL becomes the source of truth for surface/stage after non-chat surfaces no longer depend on `ChatGenerateClient`.

**Tech Stack:** React, Next.js App Router, TypeScript, Vitest + Testing Library.

---

## File Structure

- Create `apps/web/lib/chat-snapshots.ts`: sessionStorage helper functions currently embedded in `ChatGenerateClient.tsx`.
- Create `apps/web/lib/chat-snapshots.test.ts`: storage helper unit tests.
- Create `apps/web/app/generate/chat/useChatRouteRestore.ts`: route/job/thread restoration hook.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`: remove extracted helpers/effects after tests are green.
- Later tasks create surface pages such as `apps/web/app/generate/AdsSurfacePage.tsx`.

### Task 1: Extract Chat Snapshot Storage Helpers

**Files:**
- Create: `apps/web/lib/chat-snapshots.ts`
- Create: `apps/web/lib/chat-snapshots.test.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`

- [x] **Step 1: Locate exact helper block**

Run:

```bash
rg -n "CHAT_.*STORAGE_KEY|readChat|writeChat|clearChat|sessionStorage" apps/web/app/generate/chat/ChatGenerateClient.tsx
```

Expected: output includes `CHAT_FLOW_SNAPSHOT_STORAGE_KEY`, `CHAT_TURN_SNAPSHOT_STORAGE_KEY`, `CHAT_GENERATION_FAILURE_STORAGE_KEY`, and read/write/clear helpers.

- [x] **Step 2: Create the extracted module**

Create `apps/web/lib/chat-snapshots.ts` and move the storage key constants plus read/write/clear helpers from `ChatGenerateClient.tsx` without changing behavior. The module must export every helper that `ChatGenerateClient.tsx` still calls:

```ts
export const CHAT_FLOW_SNAPSHOT_STORAGE_KEY = "easyads_chat_flow_snapshot_v1";
export const CHAT_TURN_SNAPSHOT_STORAGE_KEY = "easyads_chat_turn_snapshot_v1";
export const CHAT_GENERATION_FAILURE_STORAGE_KEY = "easyads_chat_generation_failure_v1";
export const CHAT_FLOW_BACK_TARGET_STORAGE_KEY = "easyads_chat_flow_back_target_v1";

function safeSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readJsonSnapshot<T>(key: string): T | null {
  const storage = safeSessionStorage();
  if (!storage) return null;
  const raw = storage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function writeJsonSnapshot<T>(key: string, value: T): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Navigation should still work if sessionStorage is unavailable.
  }
}

export function clearJsonSnapshot(key: string): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    // Ignore storage failures.
  }
}
```

If the current helpers have narrower types, keep those typed wrappers in this file and implement them using `readJsonSnapshot`, `writeJsonSnapshot`, and `clearJsonSnapshot`.

- [x] **Step 3: Add unit tests**

Create `apps/web/lib/chat-snapshots.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import {
  CHAT_TURN_SNAPSHOT_STORAGE_KEY,
  clearJsonSnapshot,
  readJsonSnapshot,
  writeJsonSnapshot
} from "./chat-snapshots";

beforeEach(() => {
  window.sessionStorage.clear();
});

describe("chat-snapshots", () => {
  it("round-trips JSON snapshots", () => {
    writeJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY, { prompt: "카페 광고", jobId: "job_1" });

    expect(readJsonSnapshot<{ prompt: string; jobId: string }>(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toEqual({
      prompt: "카페 광고",
      jobId: "job_1"
    });
  });

  it("returns null for corrupted JSON", () => {
    window.sessionStorage.setItem(CHAT_TURN_SNAPSHOT_STORAGE_KEY, "{broken");

    expect(readJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toBeNull();
  });

  it("clears snapshots", () => {
    writeJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY, { prompt: "광고" });
    clearJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY);

    expect(readJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY)).toBeNull();
  });
});
```

- [x] **Step 4: Replace local helpers with imports**

In `apps/web/app/generate/chat/ChatGenerateClient.tsx`, remove duplicated storage helper implementations and import from `@/lib/chat-snapshots`.

- [x] **Step 5: Run tests**

Run:

```bash
cd apps/web && npx vitest run lib/chat-snapshots.test.ts app/generate/chat/ChatGenerateClient.test.tsx && npx tsc --noEmit
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/web/lib/chat-snapshots.ts apps/web/lib/chat-snapshots.test.ts apps/web/app/generate/chat/ChatGenerateClient.tsx
git commit -m "refactor(chat): extract snapshot storage helpers"
```

### Task 2: Extract Route Restoration Hook

**Files:**
- Create: `apps/web/app/generate/chat/useChatRouteRestore.ts`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Test: `apps/web/app/generate/chat/useChatRouteRestore.test.tsx`

- [ ] **Step 1: Write hook regression test**

Create `apps/web/app/generate/chat/useChatRouteRestore.test.tsx`:

```tsx
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useChatRouteRestore } from "./useChatRouteRestore";

describe("useChatRouteRestore", () => {
  it("does not switch to complete while generating route has no job id yet", () => {
    const setGenerationStage = vi.fn();

    renderHook(() =>
      useChatRouteRestore({
        initialStage: "generating",
        jobIdParam: null,
        threadIdParam: null,
        setGenerationStage,
        restoreJob: vi.fn(),
        restoreThread: vi.fn()
      })
    );

    expect(setGenerationStage).not.toHaveBeenCalledWith("complete");
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/useChatRouteRestore.test.tsx
```

Expected: FAIL because the hook does not exist.

- [ ] **Step 3: Implement hook skeleton**

Create `apps/web/app/generate/chat/useChatRouteRestore.ts`:

```ts
import { useEffect, useRef } from "react";
import type { DashboardStage } from "@/lib/dashboard-navigation";

export type GenerationStage =
  | "brief"
  | "jobQuestion"
  | "generating"
  | "browsing"
  | "complete"
  | "similarBrowsing";

export type UseChatRouteRestoreInput = {
  initialStage: DashboardStage;
  jobIdParam: string | null;
  threadIdParam: string | null;
  setGenerationStage: (stage: GenerationStage) => void;
  restoreJob: (jobId: string) => void;
  restoreThread: (threadId: string) => void;
};

function stageFromRoute(stage: DashboardStage): GenerationStage {
  if (stage === "generating") return "generating";
  if (stage === "complete") return "complete";
  if (stage === "similar") return "similarBrowsing";
  return "brief";
}

export function useChatRouteRestore(input: UseChatRouteRestoreInput): void {
  const lastPrimedStageRef = useRef<DashboardStage | null>(null);

  useEffect(() => {
    if (lastPrimedStageRef.current === input.initialStage) return;
    lastPrimedStageRef.current = input.initialStage;
    if (input.initialStage === "generating" && !input.jobIdParam) {
      return;
    }
    if (input.initialStage === "complete" && !input.jobIdParam) {
      return;
    }
    input.setGenerationStage(stageFromRoute(input.initialStage));
  }, [input.initialStage, input.jobIdParam, input.setGenerationStage]);

  useEffect(() => {
    if (!input.jobIdParam) return;
    input.restoreJob(input.jobIdParam);
  }, [input.jobIdParam, input.restoreJob]);

  useEffect(() => {
    if (!input.threadIdParam) return;
    input.restoreThread(input.threadIdParam);
  }, [input.threadIdParam, input.restoreThread]);
}
```

- [ ] **Step 4: Replace the mega-effect gradually**

In `ChatGenerateClient.tsx`, keep existing `restoreJob` and `restoreThread` bodies as local callbacks first, then call:

```tsx
useChatRouteRestore({
  initialStage,
  jobIdParam,
  threadIdParam,
  setGenerationStage,
  restoreJob: restoreGenerationJobFromRoute,
  restoreThread: restoreChatThreadFromRoute
});
```

Remove only the duplicated stage-priming portion in the first pass. Do not remove server fetch restoration logic until the tests are green.

- [ ] **Step 5: Run regression tests**

Run:

```bash
cd apps/web && npx vitest run app/generate/chat/useChatRouteRestore.test.tsx app/generate/chat/ChatGenerateClient.test.tsx && npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/generate/chat/useChatRouteRestore.ts apps/web/app/generate/chat/useChatRouteRestore.test.tsx apps/web/app/generate/chat/ChatGenerateClient.tsx
git commit -m "refactor(chat): isolate route restoration guard"
```

### Task 3: Split Ads Surface First

**Files:**
- Create: `apps/web/app/generate/AdsSurfacePage.tsx`
- Modify: `apps/web/app/ads/page.tsx`
- Test: `apps/web/app/generate/AdsSurfacePage.test.tsx`

- [ ] **Step 1: Write surface test**

Create `apps/web/app/generate/AdsSurfacePage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AdsSurfacePage } from "./AdsSurfacePage";

describe("AdsSurfacePage", () => {
  it("renders the archive surface outside ChatGenerateClient", () => {
    render(<AdsSurfacePage />);

    expect(screen.getByText(/보관함|내 찰떡 광고|광고/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd apps/web && npx vitest run app/generate/AdsSurfacePage.test.tsx
```

Expected: FAIL because the page component does not exist.

- [ ] **Step 3: Implement a thin page wrapper**

Create `apps/web/app/generate/AdsSurfacePage.tsx`:

```tsx
"use client";

import ChatGenerateClient from "./chat/ChatGenerateClient";

export function AdsSurfacePage() {
  return <ChatGenerateClient initialSurface="ads" />;
}
```

This first commit intentionally keeps behavior identical. Later commits move the ads branch internals out of `ChatGenerateClient`.

- [ ] **Step 4: Wire the route**

Change `apps/web/app/ads/page.tsx`:

```tsx
import { AdsSurfacePage } from "@/app/generate/AdsSurfacePage";

export default function AdsPage() {
  return <AdsSurfacePage />;
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd apps/web && npx vitest run app/generate/AdsSurfacePage.test.tsx app/generate/chat/ChatGenerateClient.test.tsx && npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/generate/AdsSurfacePage.tsx apps/web/app/generate/AdsSurfacePage.test.tsx apps/web/app/ads/page.tsx
git commit -m "refactor(fe): introduce ads surface wrapper"
```

## Final Verification

Run:

```bash
cd apps/web && npx vitest run app/generate/chat lib/chat-snapshots.test.ts app/generate/AdsSurfacePage.test.tsx && npx tsc --noEmit
```

Expected: PASS. Only continue extracting studio/reference surfaces after this is stable.
