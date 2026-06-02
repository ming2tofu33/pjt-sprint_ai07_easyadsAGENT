# GPT-image-2 Quality Batch v1

This document describes the guarded quality batch runner for GPT-image-2 actual generation. The goal is to collect a small evidence pack for manual image quality review, not to tune prompts in code.

## Purpose

The batch creates 3 default advertising image cases across cafe/dessert, restaurant/BBQ, and beauty/salon. Each case records the prompt, selected reference template id, expected visual template id, GenerationJob metadata, result payload, latency, and output paths.

Smoke checks answer whether an engine can be reached. This quality batch answers whether the generated image is usable as an advertisement background and what should be improved in ImagePrompt v3.

## Safety And Cost Guard

Actual generation is blocked unless all of these are true:

- `EASYADS_ENABLE_EXTERNAL_T2I=true`
- `EASYADS_ENABLE_GPT_IMAGE_2=true`
- `OPENAI_API_KEY` is present in the shell environment
- `EASYADS_QUALITY_BATCH_CONFIRM=true`
- CLI flag `--confirm-cost` is passed

The runner enforces `--max-cases` between 1 and 6. Each case always requests one image. There is no unlimited retry loop.

## Commands

Dry-run readiness report:

```bash
python scripts/run_gpt_image2_quality_batch.py --dry-run
```

Actual 3-case batch:

```bash
export EASYADS_ENABLE_EXTERNAL_T2I=true
export EASYADS_ENABLE_GPT_IMAGE_2=true
export EASYADS_QUALITY_BATCH_CONFIRM=true
python scripts/run_gpt_image2_quality_batch.py --actual --max-cases 3 --confirm-cost
```

Do not put the API key in the command line. `OPENAI_API_KEY` must already be present in the shell environment.

## Reports

Reports are written under `data/logs/`:

- `gpt_image2_quality_batch_v1_{timestamp}.json`
- `gpt_image2_quality_batch_v1_{timestamp}.md`

Generated images are written under `data/outputs/{job_id}/`. Both directories are runtime artifacts and must not be committed.

## Manual Quality Review

For each case, review the generated final image and fill in:

| Metric | Score | Notes |
|---|---:|---|
| Advertising fit | TBD |  |
| Visual quality | TBD |  |
| Not tacky | TBD |  |
| Text safe area | TBD |  |
| Reference alignment | TBD |  |
| Business fit | TBD |  |
| Fake text/logo risk | TBD |  |
| MVP usable | TBD |  |

## ImagePrompt v3 Handoff

The report has a section for failure types and ImagePrompt v3 candidates. Typical items to capture:

- fake text, signage, watermark, or logo appearing in the image
- insufficient clean area for Korean text overlay
- generic stock-like composition
- weak business fit or weak reference alignment
- tacky colors, clutter, or over-rendered props
- wrong aspect-ratio composition for the intended ad format

No raw API key, base64 image data, or image bytes should be written to the report.
