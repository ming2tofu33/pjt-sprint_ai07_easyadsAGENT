# Generated Image Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show generated archive items as an image-only viewer with a mock download affordance.

**Architecture:** Keep generated archive entries backed by session storage. Route selected generated entries to `/ads/generated-...`, render the selected image in `AdSaveFlowStep`, and hide editing-style actions for generated entries.

**Tech Stack:** Next.js App Router, React, CSS Modules, Vitest, Testing Library.

---

### Task 1: Add Regression Coverage

**Files:**
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add a test that renders `AdSaveFlowStep` with a generated creative**

Assert that the generated detail page shows `생성 이미지 보기`, the selected generated image, and `이미지 다운로드`.

- [ ] **Step 2: Run the test**

Run: `npm test -- ChatGenerateClient.test.tsx`

Expected before implementation: the new generated-image viewer assertions fail.

### Task 2: Implement Image-Only Generated Detail

**Files:**
- Modify: `apps/web/components/generate/AdSaveFlowStep.tsx`
- Modify: `apps/web/components/generate/generate.module.css`

- [ ] **Step 1: Detect generated session creatives**

Use `creative.id.startsWith("generated-")` and `creative.imageUrl`.

- [ ] **Step 2: Render generated detail as an image viewer**

Show only the generated image, a short status panel, `이미지 다운로드`, and `보관함으로 돌아가기`. Do not show quick edit, thumbnail strip, or save funnel actions.

- [ ] **Step 3: Add local mock feedback**

Clicking `이미지 다운로드` shows a small status message that this is a mock download UI until real file saving is connected.

### Task 3: Add Archive Menu Download Mock

**Files:**
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.tsx`
- Modify: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Add a generated-only menu action**

In generated archive cards, add `다운로드` to the overflow menu.

- [ ] **Step 2: Wire it to toast feedback**

Use the existing `DashboardToast` via a new `onDownloadGeneratedAd(title)` callback.

### Task 4: Verify

**Files:**
- Test: `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

- [ ] **Step 1: Run focused tests**

Run: `npm test -- ChatGenerateClient.test.tsx generated-creative-storage.test.ts ad-navigation.test.ts`

- [ ] **Step 2: Run typecheck**

Run: `npx tsc --noEmit --pretty false`

- [ ] **Step 3: Browser smoke**

Open `/ads`, click a generated item, confirm `/ads/generated-...` shows the selected image and download mock UI.
