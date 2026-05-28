# Vision Pipeline MVP

This document records the 7-B Vision Pipeline MVP scope. The source of truth remains `docs/Production_Architecture_Specification.md`; this note describes the current repository implementation.

## Scope

- Validate uploaded or referenced image paths.
- Preprocess images with PIL only.
- Save safe runtime artifacts under `data/processed/{job_id}`.
- Extract deterministic reference-style hints without VLM calls.
- Build deterministic product-preserve placeholder metadata without segmentation.
- Optionally route `build_marketing_graph()` through vision preprocessing only when image paths are present.

## Image Preprocess MVP

`orchestrator/app/vision/preprocess.py` implements:

- extension allowlist: `.jpg`, `.jpeg`, `.png`, `.webp`
- file size and pixel count limits
- EXIF orientation handling when available
- RGB conversion
- `resize_only`, `center_crop`, and `fit_with_padding`
- original copy, preprocessed PNG, and preview PNG output

Runtime paths:

- original copy: `data/processed/{job_id}/original.{ext}`
- preprocessed image: `data/processed/{job_id}/preprocessed.png`
- preview: `data/processed/{job_id}/preview.png`

`MarketingState.image_preprocess_result` stores the most recent preprocess result. When both `source_image_path` and `reference_image_path` are supplied, use `vision_pipeline_results` for the complete ordered source/reference history.

## Reference Style Stub

`extract_reference_style_stub()` uses PIL quantization and luminance statistics to produce:

- color palette
- dominant RGB colors
- brightness
- contrast hint
- basic mood keywords
- aspect-ratio layout hint
- a short `ad_style_prompt`

This is not VLM style analysis. It is deterministic metadata for prompt planning.

## Product Preserve Stub

`build_product_preserve_stub()` creates:

- a center bbox estimate
- `product_mask.png`
- `product_preview.png`
- `ProductPreserveSpec(preserve_strategy="center_bbox_stub")`

The mask is a placeholder only. No rembg, SAM, segmentation, inpainting, or image edit API is used.

## Graph Integration

`build_marketing_graph()` now routes after `input`:

- `source_image_path` -> `product_preprocess` -> optional `reference_preprocess` -> `validator`
- `reference_image_path` -> `reference_preprocess` -> `validator`
- no image path -> `validator`

The T2I-only path remains unchanged when no image path is provided.

## TLFP Metadata

`ImagePromptPlannerNode` may use `ReferenceStyleProfile.ad_style_prompt` and `ProductPreserveSpec.product_bbox` as prompt metadata hints. It still enforces:

- `must_not_include_text=true`
- `render_text_in_image=false`
- TLFP `reserved_text_areas`
- text/letters/numbers/Hangul/logo/watermark negative prompt terms

`T2IRequestBuilderNode` stores vision metadata in request metadata. It does not switch to img2img, inpainting, ControlNet, IP-Adapter, or product-preserving edit.

## Not Implemented

- real OCR
- real VLM feature extraction
- rembg
- SAM or segmentation
- ControlNet
- IP-Adapter
- inpainting
- image edit API
- product-preserving generation
- reference-guided generation beyond prompt metadata hints

## Next Steps

- Replace center bbox with real product mask generation.
- Add VLM image feature extraction behind the guarded adapter layer.
- Add product-preserving edit request schemas and routing.
- Add reference-guided prompt enhancement with structured output and cost guard.
