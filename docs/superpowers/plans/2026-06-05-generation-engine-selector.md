# Generation Engine Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users choose GPT-image-2, FLUX.1-schnell, or SD3.5 Large in the generation UI and send that choice to the existing `generation-jobs` backend.

**Architecture:** The frontend owns a friendly engine selection value, maps it to the orchestrator `runMode`, and creates a `generation-jobs` request when the user confirms the brief. The backend already routes `gpt_image_2_actual`, `flux_schnell_real`, and `sd35_large_real`, so this plan avoids backend generation logic changes.

**Tech Stack:** Next.js App Router, React client components, TypeScript, CSS modules, Vitest/Testing Library, existing BFF/orchestrator generation-jobs API.

---

## File Structure

- Create `apps/web/lib/generation-engine.ts`
  - Owns UI engine ids, labels, descriptions, and `runMode` mapping.
- Modify `apps/web/types/marketing.ts`
  - Adds selected engine to `ChatFlowState`, actions, and request option types.
- Modify `apps/web/lib/chat-flow.ts`
  - Initializes and persists the selected engine through reducer actions.
- Modify `apps/web/components/generate/ChatStartStep.tsx`
  - Adds engine selector to the chat start UI and sends the selected value.
- Modify `apps/web/components/generate/PhotoGenerateStep.tsx`
  - Adds the same selector to photo start and sends the selected value.
- Modify `apps/web/components/generate/GenerationInProgressStep.tsx`
  - Shows the selected engine while a real generation job is running.
- Modify `apps/web/components/generate/GenerationCompleteStep.tsx`
  - Shows the selected engine/result metadata in the completed result chips.
- Modify `apps/web/components/generate/generate.module.css`
  - Adds compact engine selector styling consistent with existing chips.
- Modify `apps/web/app/generate/chat/ChatGenerateClient.tsx`
  - Stores the selected engine, creates `generation-jobs` with the matching `runMode`, polls until terminal status, and stores/display real results.
- Modify tests:
  - `apps/web/lib/generation-engine.test.ts`
  - `apps/web/lib/chat-flow.test.ts`
  - `apps/web/app/generate/chat/ChatGenerateClient.test.tsx`

## Tasks

### Task 1: Add Engine Mapping Helper

- [ ] Create `apps/web/lib/generation-engine.ts`.
- [ ] Export `ImageGenerationEngine`, `GenerationRunMode`, `DEFAULT_IMAGE_GENERATION_ENGINE`, `generationEngineOptions`, `resolveGenerationRunMode`, `getGenerationEngineOption`, and `isTerminalGenerationJobStatus`.
- [ ] Add `apps/web/lib/generation-engine.test.ts` asserting:
  - `gpt_image_2` maps to `gpt_image_2_actual`.
  - `flux_schnell` maps to `flux_schnell_real`.
  - `sd35_large` maps to `sd35_large_real`.
  - unknown/null values fall back to GPT-image-2.

### Task 2: Extend Flow State and Types

- [ ] Add `imageGenerationEngine?: ImageGenerationEngine` to generation start options.
- [ ] Add `selectedImageGenerationEngine` to `ChatFlowState`.
- [ ] Extend `submitPrompt`, `backendStartSucceeded`, and a new `setImageGenerationEngine` action.
- [ ] Persist the selected engine in `GeneratedCreativeSnapshot`.
- [ ] Add chat-flow reducer tests for default and selected engine retention.

### Task 3: Add Engine Selector UI

- [ ] In `ChatStartStep`, render a compact “이미지 생성 모델” section after copy mode.
- [ ] In `PhotoGenerateStep`, render the same section after copy mode.
- [ ] Use friendly labels with visible model names:
  - `고품질 이미지` / `GPT-image-2`
  - `빠른 생성` / `FLUX.1-schnell`
  - `정교한 이미지` / `SD3.5 Large`
- [ ] Include each selected engine in `onSubmit`/`onGenerate`.

### Task 4: Connect Final Generation Job

- [ ] Import `createGenerationJob`, `getGenerationJob`, and engine helpers in `ChatGenerateClient`.
- [ ] Replace `handleOpenGeneratedResult` shell-only behavior with:
  - dispatch `generationJobRequested`
  - navigate to `chat/generating`
  - call `createGenerationJob({ userInput, threadId, entryMode, copyGenerationMode, adFormat, runMode, selectedReferenceTemplateId, metadata })`
  - poll `getGenerationJob(jobId)` until `done`, `completed`, `failed`, or `cancelled`
  - dispatch `generationJobUpdated`
  - navigate to `chat/complete`
- [ ] Keep actual-image-only policy: completed UI still renders a card only if a public preview/download URL exists.

### Task 5: Display Engine Context

- [ ] Show selected engine on the progress screen.
- [ ] Add an engine chip to the complete screen.
- [ ] Keep development artifact details only in development mode.

### Task 6: Verify

- [ ] Run focused tests:
  - `npm test -- --run app/generate/chat/ChatGenerateClient.test.tsx lib/chat-flow.test.ts lib/generation-engine.test.ts`
- [ ] Run TypeScript:
  - `npm run typecheck`
- [ ] If typecheck script is unavailable, run the repo’s existing `tsc` command for `apps/web`.
