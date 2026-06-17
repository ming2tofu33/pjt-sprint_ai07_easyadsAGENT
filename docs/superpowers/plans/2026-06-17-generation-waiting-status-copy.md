# Generation Waiting Status Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace weak loading dots and progress-bar-heavy waiting UI with state-aware Korean waiting messages that explain what the app is doing while chat, photo, brief, and image-generation requests are pending.

**Architecture:** Add a pure frontend resolver that maps `ChatFlowState` plus `GenerationJob` status/stage into user-facing waiting copy. Render that copy through one reusable waiting-status component, then use it in chat analysis, intent review, photo upload, generation progress, and pending result screens. Backend contracts remain unchanged for this pass; existing `status`, `progress.current_stage`, and job metadata drive the frontend interpretation.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS Modules, lucide-react, Vitest, Testing Library.

---

## File Structure

- Create `apps/web/lib/generation-waiting-copy.ts`: Pure status-to-copy resolver and rotation helper. It owns all Korean waiting copy and has no React dependency.
- Create `apps/web/lib/generation-waiting-copy.test.ts`: Unit tests for job stage, photo, reference, brief, and image-generation copy decisions.
- Create `apps/web/components/generate/WaitingStatusCard.tsx`: Reusable client component that displays the resolved waiting copy and rotates the current work message.
- Create `apps/web/components/generate/WaitingStatusCard.test.tsx`: Rendering and timer tests for the reusable card.
- Modify `apps/web/components/generate/generate.module.css`: Waiting-card styles and small layout helpers.
- Modify `apps/web/components/generate/ChatAnalysisPendingStep.tsx`: Replace dot-only assistant bubble with state-aware waiting card.
- Modify `apps/web/components/generate/IntentReviewStep.tsx`: Replace duplicated loading steps and loading bar with the shared waiting card.
- Modify `apps/web/components/generate/GenerationInProgressStep.tsx`: Remove the progress bar and show state-aware generation waiting copy.
- Modify `apps/web/components/generate/GenerationCompleteStep.tsx`: Use the same copy when a result page is opened while generation is still running.
- Modify `apps/web/components/generate/PhotoGenerateStep.tsx`: Show photo upload/analyze waiting copy while the first photo request is being submitted.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`: Update expectations that currently look for the old "요청을 읽고 있어요" copy.

---

### Task 1: Add Waiting Copy Resolver

**Files:**
- Create: `apps/web/lib/generation-waiting-copy.ts`
- Create: `apps/web/lib/generation-waiting-copy.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `apps/web/lib/generation-waiting-copy.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { GenerationJob } from "./api-client";
import { resolveWaitingStatusCopy, waitingMessageAt } from "./generation-waiting-copy";

function job(status: string, currentStage?: string, metadata: Record<string, unknown> = {}): GenerationJob {
  return {
    job_id: `job_${status}_${currentStage ?? "none"}`,
    status,
    progress: currentStage ? { progress_percent: 50, current_stage: currentStage } : undefined,
    metadata
  };
}

describe("generation waiting copy", () => {
  it("rotates messages by index without throwing on empty lists", () => {
    expect(waitingMessageAt(["첫 번째", "두 번째"], 0)).toBe("첫 번째");
    expect(waitingMessageAt(["첫 번째", "두 번째"], 3)).toBe("두 번째");
    expect(waitingMessageAt([], 4)).toBe("");
  });

  it("uses photo upload copy before a generation job exists", () => {
    const copy = resolveWaitingStatusCopy({ context: "photo_upload" });

    expect(copy.title).toBe("사용자의 이미지를 분석하는 중이에요");
    expect(copy.loop).toContain("사진에서 광고에 쓸 핵심 요소를 찾고 있어요");
  });

  it("uses reference-aware copy when the chat has a reference image", () => {
    const copy = resolveWaitingStatusCopy({
      context: "chat_analysis",
      state: {
        referenceImagePath: "data/uploads/reference.png",
        selectedReferenceTemplateId: null,
        sourceAssetId: null,
        sourceImagePath: null,
        generationJob: null
      }
    });

    expect(copy.title).toBe("참고 스타일을 읽고 있어요");
    expect(copy.loop).toContain("참고 이미지의 분위기와 구도를 확인하고 있어요");
  });

  it("uses image planning copy for final generation planning jobs", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation",
      generationJob: job("running", "planning", { source: "web_generation_flow" })
    });

    expect(copy.title).toBe("광고 이미지 생성 방향을 정리하고 있어요");
    expect(copy.loop).toContain("브리프를 이미지 생성 요청으로 바꾸고 있어요");
  });

  it("uses image generation copy for modal and t2i stages", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation",
      generationJob: job("running", "modal_running", { source: "web_generation_flow" })
    });

    expect(copy.title).toBe("광고 이미지를 생성하는 중이에요");
    expect(copy.loop).toContain("선택한 모델이 광고 이미지를 만들고 있어요");
  });

  it("uses answer processing copy after a generation job question is answered", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation_answer",
      generationJob: job("running", "planning")
    });

    expect(copy.title).toBe("답변을 반영하고 있어요");
    expect(copy.description).toBe("방금 보낸 답변을 작업 브리프와 생성 흐름에 반영하고 있어요.");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
npm run test -- apps/web/lib/generation-waiting-copy.test.ts
```

Expected: FAIL because `apps/web/lib/generation-waiting-copy.ts` does not exist.

- [ ] **Step 3: Implement the resolver**

Create `apps/web/lib/generation-waiting-copy.ts`:

```ts
import type { GenerationJob } from "@/lib/api-client";
import type { ChatFlowState } from "@/types/marketing";

export type WaitingStatusContext =
  | "chat_analysis"
  | "brief_refinement"
  | "photo_upload"
  | "generation"
  | "generation_answer"
  | "result_pending";

export type WaitingStatusCopy = {
  statusKey: string;
  eyebrow: string;
  title: string;
  description: string;
  loop: readonly string[];
};

type WaitingStateInput = Partial<
  Pick<
    ChatFlowState,
    | "generationJob"
    | "referenceImagePath"
    | "selectedReferenceTemplateId"
    | "sourceAssetId"
    | "sourceImagePath"
    | "copyGenerationMode"
  >
>;

type ResolveWaitingCopyInput = {
  context: WaitingStatusContext;
  state?: WaitingStateInput | null;
  generationJob?: GenerationJob | null;
};

const chatAnalysisCopy: WaitingStatusCopy = {
  statusKey: "chat_analysis",
  eyebrow: "요청 분석",
  title: "요청 내용을 분석하고 있어요",
  description: "입력한 내용을 읽고 광고 제작에 필요한 정보를 정리하고 있어요.",
  loop: ["요청 문장에서 업종과 상품을 찾고 있어요", "부족한 정보가 있는지 확인하고 있어요", "다음 질문을 준비하고 있어요"]
};

const referenceAnalysisCopy: WaitingStatusCopy = {
  statusKey: "reference_analysis",
  eyebrow: "샘플 분석",
  title: "참고 스타일을 읽고 있어요",
  description: "선택한 샘플이나 참고 이미지의 분위기를 광고 요청에 연결하고 있어요.",
  loop: ["참고 이미지의 분위기와 구도를 확인하고 있어요", "광고에 반영할 스타일 힌트를 정리하고 있어요", "요청 내용과 참고 스타일을 맞춰보고 있어요"]
};

const photoAnalysisCopy: WaitingStatusCopy = {
  statusKey: "photo_analysis",
  eyebrow: "사진 분석",
  title: "사용자의 이미지를 분석하는 중이에요",
  description: "올린 사진에서 광고에 사용할 요소와 이미지 생성 방향을 찾고 있어요.",
  loop: ["사진에서 광고에 쓸 핵심 요소를 찾고 있어요", "상품이 잘 보이도록 이미지 방향을 정리하고 있어요", "사진과 요청 내용을 함께 확인하고 있어요"]
};

const briefCopy: WaitingStatusCopy = {
  statusKey: "brief_refinement",
  eyebrow: "브리프 정리",
  title: "작업 브리프를 완성하고 있어요",
  description: "선택한 문구, 채널, 분위기를 바탕으로 이미지 생성 전 브리프를 정리하고 있어요.",
  loop: ["광고 목적과 상품 정보를 정리하고 있어요", "이미지에 들어갈 문구를 확인하고 있어요", "생성 요청에 맞는 브리프를 만들고 있어요"]
};

const answerCopy: WaitingStatusCopy = {
  statusKey: "generation_answer",
  eyebrow: "답변 반영",
  title: "답변을 반영하고 있어요",
  description: "방금 보낸 답변을 작업 브리프와 생성 흐름에 반영하고 있어요.",
  loop: ["답변 내용을 작업 상태에 저장하고 있어요", "다음 생성 단계를 다시 확인하고 있어요", "필요한 경우 다음 질문을 준비하고 있어요"]
};

const imagePlanningCopy: WaitingStatusCopy = {
  statusKey: "image_planning",
  eyebrow: "이미지 준비",
  title: "광고 이미지 생성 방향을 정리하고 있어요",
  description: "확정된 브리프를 이미지 생성 모델이 이해할 수 있는 요청으로 바꾸고 있어요.",
  loop: ["브리프를 이미지 생성 요청으로 바꾸고 있어요", "스타일과 구도 힌트를 정리하고 있어요", "광고 이미지에 필요한 문구와 여백을 확인하고 있어요"]
};

const imageGeneratingCopy: WaitingStatusCopy = {
  statusKey: "image_generating",
  eyebrow: "이미지 생성",
  title: "광고 이미지를 생성하는 중이에요",
  description: "선택한 이미지 모델이 브리프와 스타일 힌트를 바탕으로 광고 이미지를 만들고 있어요.",
  loop: ["선택한 모델이 광고 이미지를 만들고 있어요", "스타일과 구도를 이미지에 반영하고 있어요", "완성된 이미지 품질을 확인할 준비를 하고 있어요"]
};

const storageCopy: WaitingStatusCopy = {
  statusKey: "storage_pending",
  eyebrow: "저장 확인",
  title: "보관함 연결을 확인하고 있어요",
  description: "완성된 이미지를 보관함에서 열 수 있도록 저장 정보를 확인하고 있어요.",
  loop: ["완성된 이미지 주소를 확인하고 있어요", "보관함에 연결할 정보를 정리하고 있어요", "결과 화면에 보여줄 정보를 준비하고 있어요"]
};

const failedCopy: WaitingStatusCopy = {
  statusKey: "failed",
  eyebrow: "오류 확인",
  title: "생성 상태를 확인하고 있어요",
  description: "작업 중 문제가 생겼는지 확인하고 다시 시도할 수 있는 상태로 정리하고 있어요.",
  loop: ["오류 내용을 확인하고 있어요", "입력 내용을 유지한 채 복구할 방법을 찾고 있어요"]
};

export function waitingMessageAt(messages: readonly string[], tick: number): string {
  if (messages.length === 0) {
    return "";
  }
  const safeTick = Number.isFinite(tick) ? Math.max(0, Math.floor(tick)) : 0;
  return messages[safeTick % messages.length] ?? messages[0] ?? "";
}

export function resolveWaitingStatusCopy(input: ResolveWaitingCopyInput): WaitingStatusCopy {
  const state = input.state ?? null;
  const job = input.generationJob ?? state?.generationJob ?? null;
  const status = normalize(job?.status);
  const stage = normalize(job?.progress?.current_stage ?? job?.current_stage ?? job?.status);

  if (status === "failed" || stage === "failed") {
    return failedCopy;
  }

  if (input.context === "photo_upload") {
    return photoAnalysisCopy;
  }

  if (input.context === "brief_refinement") {
    return briefCopy;
  }

  if (input.context === "generation_answer") {
    return answerCopy;
  }

  if (status === "done" || status === "completed" || stage === "completed") {
    return storageCopy;
  }

  if (input.context === "result_pending") {
    return isImageStage(stage) ? imageGeneratingCopy : storageCopy;
  }

  if (isImageStage(stage)) {
    return imageGeneratingCopy;
  }

  const isFinalGeneration = isFinalImageGenerationJob(job) || input.context === "generation";
  if (isFinalGeneration) {
    return imagePlanningCopy;
  }

  if (hasSourcePhoto(state)) {
    return photoAnalysisCopy;
  }

  if (hasReference(state)) {
    return referenceAnalysisCopy;
  }

  return chatAnalysisCopy;
}

function normalize(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function isFinalImageGenerationJob(job: GenerationJob | null | undefined): boolean {
  const metadata = asRecord(job?.metadata);
  const finalBrief = asRecord(metadata.final_brief ?? metadata.finalBrief);
  return metadata.source === "web_generation_flow" || Object.keys(finalBrief).length > 0;
}

function hasSourcePhoto(state: WaitingStateInput | null): boolean {
  return Boolean(state?.sourceAssetId || state?.sourceImagePath);
}

function hasReference(state: WaitingStateInput | null): boolean {
  return Boolean(state?.referenceImagePath || state?.selectedReferenceTemplateId);
}

function isImageStage(stage: string): boolean {
  return [
    "rendering",
    "t2i_running",
    "generating_image",
    "modal_submitted",
    "modal_running",
    "background_generation",
    "final_rendering"
  ].includes(stage);
}
```

- [ ] **Step 4: Run the resolver tests**

Run:

```bash
npm run test -- apps/web/lib/generation-waiting-copy.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/generation-waiting-copy.ts apps/web/lib/generation-waiting-copy.test.ts
git commit -m "feat(fe): add generation waiting copy resolver"
```

---

### Task 2: Add Reusable Waiting Status Card

**Files:**
- Create: `apps/web/components/generate/WaitingStatusCard.tsx`
- Create: `apps/web/components/generate/WaitingStatusCard.test.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Write the failing component test**

Create `apps/web/components/generate/WaitingStatusCard.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";

const copy: WaitingStatusCopy = {
  statusKey: "test_waiting",
  eyebrow: "테스트 상태",
  title: "작업을 확인하고 있어요",
  description: "사용자에게 지금 어떤 작업 중인지 알려줘요.",
  loop: ["첫 번째 작업 중이에요", "두 번째 작업 중이에요"]
};

afterEach(() => {
  vi.useRealTimers();
});

describe("WaitingStatusCard", () => {
  it("renders status copy with polite live updates", () => {
    render(<WaitingStatusCard copy={copy} />);

    expect(screen.getByText("테스트 상태")).toBeTruthy();
    expect(screen.getByText("작업을 확인하고 있어요")).toBeTruthy();
    expect(screen.getByText("사용자에게 지금 어떤 작업 중인지 알려줘요.")).toBeTruthy();
    expect(screen.getByText("첫 번째 작업 중이에요")).toBeTruthy();
    expect(screen.getByLabelText("작업 대기 상태")).toHaveAttribute("aria-live", "polite");
  });

  it("rotates the visible waiting message", () => {
    vi.useFakeTimers();
    render(<WaitingStatusCard copy={copy} intervalMs={1000} />);

    expect(screen.getByText("첫 번째 작업 중이에요")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByText("두 번째 작업 중이에요")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the component test to verify it fails**

Run:

```bash
npm run test -- apps/web/components/generate/WaitingStatusCard.test.tsx
```

Expected: FAIL because `WaitingStatusCard.tsx` does not exist.

- [ ] **Step 3: Implement the card**

Create `apps/web/components/generate/WaitingStatusCard.tsx`:

```tsx
"use client";

import { LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { WaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { waitingMessageAt } from "@/lib/generation-waiting-copy";
import styles from "./generate.module.css";

type WaitingStatusCardProps = {
  copy: WaitingStatusCopy;
  compact?: boolean;
  className?: string;
  intervalMs?: number;
};

export function WaitingStatusCard({ copy, compact = false, className = "", intervalMs = 2600 }: WaitingStatusCardProps) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setTick(0);
    if (copy.loop.length <= 1) {
      return undefined;
    }
    const interval = window.setInterval(() => setTick((current) => current + 1), intervalMs);
    return () => window.clearInterval(interval);
  }, [copy.statusKey, copy.loop.length, intervalMs]);

  const currentMessage = useMemo(() => waitingMessageAt(copy.loop, tick), [copy.loop, tick]);
  const classNames = [styles.waitingStatusCard, compact ? styles.waitingStatusCardCompact : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={classNames} data-status-key={copy.statusKey} data-compact={compact ? "true" : "false"} aria-label="작업 대기 상태" aria-live="polite">
      <span className={styles.waitingStatusIcon} aria-hidden="true">
        <Sparkles size={16} />
        <LoaderCircle size={17} />
      </span>
      <div className={styles.waitingStatusText}>
        <span className={styles.waitingStatusEyebrow}>{copy.eyebrow}</span>
        <strong>{copy.title}</strong>
        <p>{copy.description}</p>
        {currentMessage ? <small>{currentMessage}</small> : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add CSS for the card**

Append these styles near the existing loading/status styles in `apps/web/components/generate/generate.module.css`:

```css
.waitingStatusCard {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 16px;
  border: 1px solid rgba(17, 185, 129, 0.24);
  border-radius: 8px;
  background: #ecfdf5;
  color: #0f172a;
}

.waitingStatusCardCompact {
  padding: 13px 14px;
}

.waitingStatusIcon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #ffffff;
  color: #059669;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.waitingStatusIcon svg:last-child {
  position: absolute;
  right: -2px;
  bottom: -2px;
  color: #111827;
  animation: waitingStatusSpin 1.2s linear infinite;
}

.waitingStatusText {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.waitingStatusEyebrow {
  font-size: 11px;
  font-weight: 800;
  color: #059669;
}

.waitingStatusText strong {
  font-size: 16px;
  line-height: 1.35;
  letter-spacing: 0;
}

.waitingStatusText p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
}

.waitingStatusText small {
  display: inline-flex;
  width: fit-content;
  max-width: 100%;
  padding: 6px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  color: #065f46;
}

@keyframes waitingStatusSpin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
```

- [ ] **Step 5: Run the component test**

Run:

```bash
npm run test -- apps/web/components/generate/WaitingStatusCard.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/generate/WaitingStatusCard.tsx apps/web/components/generate/WaitingStatusCard.test.tsx apps/web/components/generate/generate.module.css
git commit -m "feat(fe): add reusable waiting status card"
```

---

### Task 3: Replace Chat Analysis Pending UI

**Files:**
- Modify: `apps/web/components/generate/ChatAnalysisPendingStep.tsx`
- Modify: `apps/web/components/generate/IntentReviewStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Update tests that assert old copy**

In `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`, replace assertions that match `/요청을 읽고 있어요/` with the new stable title:

```tsx
expect(screen.getByText(/요청 내용을 분석하고 있어요/)).toBeTruthy();
```

For tests that assert the old pending step exists more than once, keep the same test structure and change only the expected text. Do not remove the negative assertion for `"생성 결과를 준비하고 있어요"` if it is still testing the analysis screen.

- [ ] **Step 2: Run the affected test to verify failure before UI changes**

Run:

```bash
npm run test -- apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: FAIL because the UI still renders the old "요청을 읽고 있어요" text.

- [ ] **Step 3: Replace `ChatAnalysisPendingStep` content**

Change `apps/web/components/generate/ChatAnalysisPendingStep.tsx` to:

```tsx
"use client";

import type { ChatFlowState } from "@/types/marketing";
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { ChatTimelineStep } from "./ChatTimelineStep";
import { WaitingStatusCard } from "./WaitingStatusCard";

type ChatAnalysisPendingStepProps = {
  state: ChatFlowState;
  onBack: () => void;
  onDelete?: () => void;
};

export function ChatAnalysisPendingStep({ state, onBack, onDelete }: ChatAnalysisPendingStepProps) {
  const waitingCopy = resolveWaitingStatusCopy({
    state,
    context: state.step >= 4 ? "generation_answer" : "chat_analysis"
  });

  return (
    <ChatTimelineStep state={state} onBack={onBack} onDelete={onDelete}>
      <WaitingStatusCard copy={waitingCopy} />
    </ChatTimelineStep>
  );
}
```

- [ ] **Step 4: Refactor `IntentReviewStep` loading block**

In `apps/web/components/generate/IntentReviewStep.tsx`, remove this constant:

```ts
const loadingAnalysisSteps = ["요청 문장 읽는 중", "필요한 정보 찾는 중", "다음 질문 준비 중"];
```

Add imports:

```ts
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";
```

Inside `IntentReviewCard`, add this before `return`:

```ts
  const waitingCopy = resolveWaitingStatusCopy({ state, context: "chat_analysis" });
```

Replace the `state.isLoading ? (...)` branch inside `contextCard` with:

```tsx
        {state.isLoading ? (
          <>
            <p className={styles.contextSourceNote}>{waitingCopy.description}</p>
            <WaitingStatusCard copy={waitingCopy} compact />
          </>
        ) : (
```

Replace the loading helper text in the footer with:

```tsx
        ) : state.isLoading ? (
          <p className={styles.helperText}>{waitingCopy.title}</p>
        ) : !hasBackendSession ? (
```

- [ ] **Step 5: Run the chat client test**

Run:

```bash
npm run test -- apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS with the new waiting copy expectations.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/generate/ChatAnalysisPendingStep.tsx apps/web/components/generate/IntentReviewStep.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
git commit -m "feat(fe): show state-aware chat analysis waiting copy"
```

---

### Task 4: Replace Generation Progress Bar With State Copy

**Files:**
- Modify: `apps/web/components/generate/GenerationInProgressStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/lib/generation-job-stage.test.ts`

- [ ] **Step 1: Update expectations around progress percent**

In `apps/web/lib/generation-job-stage.test.ts`, keep the existing test that verifies backend percent is parsed because other screens may still consume it. Add this test to document that waiting copy is separate from percent display:

```ts
import { resolveWaitingStatusCopy } from "./generation-waiting-copy";
```

Add the test case:

```ts
  it("keeps waiting copy independent from backend progress percent", () => {
    const copy = resolveWaitingStatusCopy({
      context: "generation",
      generationJob: {
        job_id: "job_progress_copy",
        status: "running",
        progress: {
          progress_percent: 72,
          current_stage: "modal_running"
        },
        metadata: { source: "web_generation_flow" }
      }
    });

    expect(copy.title).toBe("광고 이미지를 생성하는 중이에요");
    expect(copy.loop).toContain("선택한 모델이 광고 이미지를 만들고 있어요");
  });
```

- [ ] **Step 2: Run the focused tests**

Run:

```bash
npm run test -- apps/web/lib/generation-job-stage.test.ts apps/web/lib/generation-waiting-copy.test.ts
```

Expected: PASS. This is a regression guard before modifying UI.

- [ ] **Step 3: Modify `GenerationInProgressStep`**

In `apps/web/components/generate/GenerationInProgressStep.tsx`, add imports:

```ts
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";
```

Inside the component, add:

```ts
  const waitingCopy = resolveWaitingStatusCopy({ state, context: "generation" });
```

Replace this whole block:

```tsx
      <div className={styles.generationProgress}>
        <div className={styles.progressMeta}>
          <strong>현재 상태</strong>
          <span>
            {generationStage.label}
            {generationStage.progressPercent !== null ? <strong>{generationStage.progressPercent}%</strong> : null}
          </span>
        </div>
        <span
          className={`${styles.progressTrack} ${generationStage.progressPercent === null ? styles.indeterminateProgressTrack : ""}`}
          aria-hidden="true"
        >
          <span
            className={styles.progressBar}
            style={generationStage.progressPercent === null ? undefined : { width: `${generationStage.progressPercent}%` }}
          />
        </span>
        <p>{generationStage.detail}</p>
      </div>
```

with:

```tsx
      <WaitingStatusCard copy={waitingCopy} />
```

- [ ] **Step 4: Modify `GenerationCompleteStep` pending state**

In `apps/web/components/generate/GenerationCompleteStep.tsx`, add imports:

```ts
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";
```

Inside the component after `const generatedJob = state.generationJob ?? null;`, add:

```ts
  const waitingCopy = resolveWaitingStatusCopy({ state, context: "result_pending" });
```

Inside the `isInProgress ? (...)` branch, replace the `pendingPreviewFrame` contents:

```tsx
          <div className={styles.pendingPreviewFrame}>
            <LoaderCircle size={26} aria-hidden="true" />
            <strong>미리보기는 완성 후 표시돼요</strong>
            <p>이미지가 준비되면 이 영역이 결과 카드로 바뀝니다.</p>
          </div>
```

with:

```tsx
          <div className={styles.pendingPreviewFrame}>
            <WaitingStatusCard copy={waitingCopy} compact />
          </div>
```

- [ ] **Step 5: Run relevant tests**

Run:

```bash
npm run test -- apps/web/lib/generation-job-stage.test.ts apps/web/components/generate/GenerationCompleteStep.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/generate/GenerationInProgressStep.tsx apps/web/components/generate/GenerationCompleteStep.tsx apps/web/lib/generation-job-stage.test.ts
git commit -m "feat(fe): replace generation progress bar with status copy"
```

---

### Task 5: Show Photo Submission Waiting Copy

**Files:**
- Modify: `apps/web/components/generate/PhotoGenerateStep.tsx`

- [ ] **Step 1: Add a focused component assertion**

If `PhotoGenerateStep` does not already have a component test file, create `apps/web/components/generate/PhotoGenerateStep.test.tsx` with this test:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PhotoGenerateStep } from "./PhotoGenerateStep";

function file() {
  return new File(["fake"], "menu.png", { type: "image/png" });
}

describe("PhotoGenerateStep", () => {
  it("shows photo analysis waiting copy while submitting", async () => {
    const onGenerate = vi.fn(() => new Promise<void>(() => undefined));
    render(<PhotoGenerateStep onBack={vi.fn()} onGoHome={vi.fn()} onOpenChat={vi.fn()} onGenerate={onGenerate} />);

    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file()] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), { target: { value: "이 사진으로 신메뉴 광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("사진 기반 생성 시작"));

    await waitFor(() => {
      expect(screen.getByText("사용자의 이미지를 분석하는 중이에요")).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Run the photo test to verify failure**

Run:

```bash
npm run test -- apps/web/components/generate/PhotoGenerateStep.test.tsx
```

Expected: FAIL because the waiting copy is not rendered during `isSubmitting`.

- [ ] **Step 3: Add waiting copy to `PhotoGenerateStep`**

In `apps/web/components/generate/PhotoGenerateStep.tsx`, add imports:

```ts
import { resolveWaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { WaitingStatusCard } from "./WaitingStatusCard";
```

Inside `PhotoGenerateStep`, add this after state declarations:

```ts
  const photoWaitingCopy = resolveWaitingStatusCopy({ context: "photo_upload" });
```

Render the waiting card immediately before the existing `SmartChatInput`:

```tsx
        {isSubmitting ? <WaitingStatusCard copy={photoWaitingCopy} compact /> : null}

        <SmartChatInput
```

- [ ] **Step 4: Run the photo test**

Run:

```bash
npm run test -- apps/web/components/generate/PhotoGenerateStep.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/generate/PhotoGenerateStep.tsx apps/web/components/generate/PhotoGenerateStep.test.tsx
git commit -m "feat(fe): show photo analysis waiting copy"
```

---

### Task 6: Final Verification

**Files:**
- Verify changed frontend files and tests only.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
npm run test -- apps/web/lib/generation-waiting-copy.test.ts apps/web/components/generate/WaitingStatusCard.test.tsx apps/web/components/generate/PhotoGenerateStep.test.tsx apps/web/components/generate/GenerationCompleteStep.test.tsx apps/web/app/generate/chat/ChatGenerateClient.test.tsx
```

Expected: PASS. Existing React `act(...)` warnings can remain if the same warnings already existed before this work.

- [ ] **Step 2: Run lint**

Run:

```bash
npm run lint
```

Expected: PASS. Existing warnings in unrelated files can remain; do not broaden this task into warning cleanup.

- [ ] **Step 3: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Inspect waiting UI manually**

Run the app:

```bash
npm run dev -- --port 3004
```

Open:

```text
http://localhost:3004/generate/chat
```

Manual checks:

- Submitting a chat prompt shows "요청 내용을 분석하고 있어요" instead of dot-only loading.
- Submitting with a reference image shows "참고 스타일을 읽고 있어요".
- Submitting a photo from "내 사진으로 만들기" shows "사용자의 이미지를 분석하는 중이에요" while the request is pending.
- The final generation screen shows "광고 이미지 생성 방향을 정리하고 있어요" or "광고 이미지를 생성하는 중이에요" depending on job stage.
- No visible progress bar appears in the final generation waiting screen.

- [ ] **Step 5: Commit verification fixes if any test-driven adjustment was needed**

If the verification step required code changes, stage only the touched files and commit:

```bash
git add apps/web/lib/generation-waiting-copy.ts apps/web/lib/generation-waiting-copy.test.ts apps/web/components/generate/WaitingStatusCard.tsx apps/web/components/generate/WaitingStatusCard.test.tsx apps/web/components/generate/ChatAnalysisPendingStep.tsx apps/web/components/generate/IntentReviewStep.tsx apps/web/components/generate/GenerationInProgressStep.tsx apps/web/components/generate/GenerationCompleteStep.tsx apps/web/components/generate/PhotoGenerateStep.tsx apps/web/components/generate/PhotoGenerateStep.test.tsx apps/web/components/generate/generate.module.css apps/web/app/generate/chat/ChatGenerateClient.test.tsx apps/web/lib/generation-job-stage.test.ts
git commit -m "test(fe): verify generation waiting status copy"
```

If no code changed during verification, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers state-aware copy, no progress bar on generation wait, chat/photo/brief/generation pending surfaces, and frontend tests. It intentionally avoids backend schema changes because existing `status`, `progress.current_stage`, and metadata are enough for the first improvement.
- Placeholder scan: The plan contains concrete file paths, code blocks, commands, expected outcomes, and commit commands. It does not rely on unspecified future work.
- Type consistency: `WaitingStatusContext`, `WaitingStatusCopy`, `resolveWaitingStatusCopy`, and `waitingMessageAt` are defined in Task 1 and reused with the same names in later tasks.
