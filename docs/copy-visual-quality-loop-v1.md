# Copy Visual Quality Loop v1

## 1. Purpose

This pass validates whether generated backgrounds can become usable ad drafts after deterministic Korean copy overlay. It does not generate new backgrounds and does not call GPT-image-2, SD3.5, FLUX, LLM, VLM, OCR, rembg, or SAM.

The loop uses existing `gpt_image2_quality_batch_v1` artifacts when available, overlays sample copy, and records rule-based contrast, safe-area, clipping, and copy-tone findings.

## 2. Copy Tone Policy

`orchestrator/app/llm/copy_tone_policy.py` defines deterministic policies for:

- `cafe`
- `restaurant_bbq`
- `beauty_skincare`
- `beauty_hair`
- `beauty_nail`
- `beauty_spa`
- `generic`

Each policy defines length limits, preferred tone, avoid terms, CTA candidates, promotion style, and visual fit notes. Generated copy can be normalized. `custom_input` copy is not rewritten; it is only scored and annotated with warnings.

## 3. Overlay Preview Runner

`python scripts/run_copy_visual_overlay_review.py --dry-run` creates a readiness report without requiring local image artifacts.

`python scripts/run_copy_visual_overlay_review.py --max-cases 3` reads the latest `data/logs/gpt_image2_quality_batch_v1_*.json`, overlays copy onto existing `final_0.png` files, and writes:

- `data/outputs/{job_id}/copy_visual_preview_0.png`
- `data/logs/copy_visual_quality_loop_v1_{timestamp}.json`
- `data/logs/copy_visual_quality_loop_v1_{timestamp}.md`

These runtime artifacts stay ignored and are not committed.

## 4. Validation Signals

The validator uses PIL pixel statistics only:

- contrast ratio estimate from text color and background luminance
- safe-area complexity from grayscale standard deviation
- clipping checks from renderer text boxes against canvas bounds
- plate/shadow recommendations for bright or low-contrast areas

No OCR or VLM scoring is used in this pass.

## 5. Current Findings

Based on the v1 quality review, cafe and restaurant backgrounds are likely usable for overlay previews with controlled copy length. Restaurant copy benefits from reservation-oriented CTA language. Cafe copy should avoid discount-heavy phrasing and stay seasonal/new-menu focused.

Beauty backgrounds require stricter plate/shadow handling because bright studio-style compositions can reduce text contrast. Beauty subtype copy must avoid medical or guaranteed-effect claims and should use consultation-oriented CTAs.

## 6. Improvement Candidates

### Copy

- Keep generated headlines within 18 Korean characters.
- Prefer reservation or consultation CTAs by business type.
- Remove low-cost flyer phrases and exaggerated claims before rendering.
- Preserve custom input exactly and surface warnings instead of rewriting.

### Visual

- Ask GPT-image-2 v3 prompts for lower-detail negative space where copy will sit.
- For beauty, reserve a cleaner bright plate zone or render with a translucent text plate.
- For restaurant, keep warm dark negative space usable for cream/white text.

### Layout

- Use ratio-based text areas so 1:1 and 9:16 assets can diverge later.
- Treat `copy_visual_preview_0.png` as a review artifact, not a public serving path.
- Track clipping from actual rendered text boxes, not only planned safe areas.

## 7. Next Step

Run a GPT-image-2 v3 mini batch after ImagePrompt v3 and copy tone policy changes are applied. Compare v1 and v3 on text-safe-area quality, fake text risk, business fit, and final copy overlay usability.
