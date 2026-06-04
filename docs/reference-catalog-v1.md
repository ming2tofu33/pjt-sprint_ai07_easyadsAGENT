# Reference Catalog Backend v1

## Purpose

Reference Catalog Backend v1 provides a deterministic backend foundation for selecting reference templates before advertising image generation. It does not implement a frontend gallery, FastAPI endpoint, database, vector search, or external template ingestion.

## Current Scope

- Pydantic schemas for reference template metadata.
- Seed catalog with internal mock metadata only.
- In-memory search, filter, detail lookup, and similar-template recommendation.
- `selected_reference_template_id` support in `InitialMarketingRequest` and `MarketingState`.
- Optional LangGraph route that resolves a template before image/reference preprocessing.
- Metadata hints passed into `ImagePromptPlannerNode` and `T2IRequest.metadata`.

## ReferenceTemplate Schema

`ReferenceTemplate` stores:

- identity: `template_id`, `title`, `description`
- taxonomy: `category`, `sub_category`, `tags`, `business_types`
- format: `ad_formats`, `platforms`, `aspect_ratio`, `width`, `height`
- assets: `thumbnail_path`, `preview_path`, `source_image_path`
- style hints: `style_keywords`, `color_palette`, `layout_hint`, `typography_hint`, `background_style`
- lifecycle: `status`, `source`, `license_note`

Seed asset paths are placeholders. No external design assets are included.

## Seed Catalog

The catalog starts with 10 mock templates across cafe, restaurant, beauty, fitness, retail, event, flyer, instagram feed/story, and banner categories.

The seed entries are internal metadata examples. They do not copy Canva, MiriCanvas, or other third-party templates.

Current seed taxonomy intentionally includes a few format/channel-like categories such as `instagram_feed`, `instagram_story`, `banner`, and `flyer` for MVP filter coverage. Before production gallery design, normalize taxonomy so `category` means industry or theme, `ad_formats` means output format, and `platforms` means delivery channel.

## Search And Filters

`search_reference_templates()` supports:

- keyword search over title, description, category, tags, style keywords, and business types
- category exact match
- business type list contains
- ad format list contains
- platform list contains
- aspect ratio exact match
- tags and style keywords contains
- active-only filtering
- `popular`, `recent`, `title`, and `relevance` sorting
- limit/offset pagination

## Similar Templates

`find_similar_templates()` uses deterministic rule scoring:

- same category: +3
- same ad format: +3
- same aspect ratio: +2
- tag overlap: +1 each
- style keyword overlap: +1 each
- business type overlap: +1 each
- popularity score as a small tie breaker

No vector DB or Qdrant is used.

## selected_reference_template_id Flow

When `selected_reference_template_id` is present:

1. `reference_template_resolve_node` resolves the template from the seed catalog.
2. `selected_reference_template` and `reference_template_selection` are stored in state.
3. Template style hints are written to `current_brief`.
4. A `reference_template` artifact ref is appended.
5. If the template has `assets.source_image_path`, it is copied to `reference_image_path`.
6. If no source image exists, graph execution continues with metadata-only style hints.

Direct `reference_image_path` input remains supported.

## Vision Pipeline Connection

If a resolved template supplies a real `source_image_path`, the existing `reference_preprocess_node` can run. Seed templates currently omit actual source images, so they act as metadata-only references.

## TLFP / T2I Metadata

Template style keywords, palette, layout hint, typography hint, and full template metadata are passed to:

- `ImagePromptPlannerNode`
- `T2IRequest.metadata`

For v1, full selected template metadata is kept in `T2IRequest.metadata` for traceability. A later production cleanup should slim this to `template_id`, `title`, `style_keywords`, `color_palette`, `layout_hint`, `typography_hint`, and `background_style`.

Safety constraints remain unchanged:

- `must_not_include_text=true`
- `render_text_in_image=false`
- reserved text areas preserved
- negative prompts keep text/letters/numbers/Hangul/logo/watermark restrictions

Seed asset paths are placeholders. This backend catalog does not imply that template thumbnails/previews are currently served to the frontend. Actual asset storage and serving remain separate work.

## Not Implemented

- real database
- real object storage
- FastAPI endpoint
- FE gallery
- template editor
- Qdrant or vector search
- external template scraping
- Canva/MiriCanvas asset collection
- copyrighted template image ingestion
- VLM-based style extraction
- reference-conditioned image generation

## Follow-Up Cleanup

- Normalize category/ad format/platform taxonomy before real gallery UX work.
- Add actual template asset storage and serving.
- Slim template metadata in T2I request traces when the catalog grows.
- Document or filter accumulated Pillow/SWIG pytest warnings if CI starts treating warnings as failures.
