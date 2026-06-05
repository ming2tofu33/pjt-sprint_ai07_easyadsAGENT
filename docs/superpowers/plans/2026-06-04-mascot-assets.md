# Mascot Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the five local mascot sheets into transparent PNG assets, regenerate clean chroma-keyed mascot cutouts where white-on-white removal failed, and apply selected mascot states to the EasyAds mobile web flows.

**Architecture:** Keep raster assets in `apps/web/public/mascots/`, expose stable role-based paths through a small TypeScript mapping, and render them through one reusable `MascotImage` component. Replace only large emotional/status illustrations while preserving lucide icons for controls and buttons.

**Tech Stack:** Next.js 14, React 18, CSS Modules, PNG assets, local Python/Pillow image processing.

---

### Task 1: Generate Project Mascot Assets

**Files:**
- Create: `apps/web/public/mascots/*.png`
- Create: `apps/web/public/mascots-regenerated-full/*.png`
- Create: `tmp/mascot-reference-crops/*.png`
- Create: `tmp/mascot-regenerated-full/*.png`

- [x] **Step 1: Crop selected sheet cells**

Run a Pillow-based local script that crops the approved cells from `images/개떡찰떡아이콘1.png` through `images/개떡찰떡아이콘5.png`.

- [x] **Step 2: Regenerate clean chroma-keyed cutouts**

Use image generation from each crop reference to recreate the mascot on a removable magenta chroma-key background, avoiding the white-body loss from white-background alpha extraction.

- [x] **Step 3: Remove backgrounds**

Remove magenta with local chroma-key post-processing, trim/pad each asset, and normalize output dimensions for web use.

- [x] **Step 4: Validate alpha**

Run a PNG validation command to confirm every output is RGBA and has transparent corners.

### Task 2: Add Mascot Rendering API

**Files:**
- Create: `apps/web/lib/mascot-assets.ts`
- Create: `apps/web/components/generate/MascotImage.tsx`

- [x] **Step 1: Define role-based mascot paths**

Create named roles such as `homeReady`, `search`, `upload`, `generating`, `complete`, `error`, `brand`, and `notification`.

- [x] **Step 2: Render assets with Next Image**

Create a small component that accepts a role, alt text, size class, and optional decorative flag.

### Task 3: Apply Mascots To Screens

**Files:**
- Modify: `apps/web/components/generate/HomeStartStep.tsx`
- Modify: `apps/web/components/generate/PhotoGenerateStep.tsx`
- Modify: `apps/web/components/generate/ReferenceBrowseStep.tsx`
- Modify: `apps/web/components/generate/GenerationInProgressStep.tsx`
- Modify: `apps/web/components/generate/GenerationCompleteStep.tsx`
- Modify: `apps/web/components/generate/ExceptionStateStep.tsx`
- Modify: `apps/web/components/generate/BrandKitFlowStep.tsx`
- Modify: `apps/web/components/generate/NotificationCenterStep.tsx`
- Modify: `apps/web/components/generate/NotificationDetailStep.tsx`
- Modify: `apps/web/components/generate/AdSaveFlowStep.tsx`
- Modify: `apps/web/components/generate/RecentAdsStep.tsx`
- Modify: `apps/web/components/generate/CopyChannelStep.tsx`

- [x] **Step 1: Replace large CSS/lucide-only illustrations**

Use mascot art on home hero, empty states, upload state, generating state, completion state, save completion, brand start/complete, and notification detail.

- [x] **Step 2: Preserve controls**

Keep existing lucide icons inside buttons, tabs, filters, and small controls.

### Task 4: Style And Verify

**Files:**
- Modify: `apps/web/components/generate/generate.module.css`

- [x] **Step 1: Add stable mascot dimensions**

Add fixed image containers for hero, empty panels, upload panels, and notification/brand heroes.

- [x] **Step 2: Run checks**

Run `npm run test -- --runInBand` if supported or `npm run test`; run `npm run lint` if the project lint script is available.

- [x] **Step 3: Start local server**

Run the web dev server and report the local URL for visual inspection.
