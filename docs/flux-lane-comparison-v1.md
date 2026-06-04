# FLUX Lane Comparison v1

## Purpose

This milestone adds FLUX as a guarded local T2I candidate and creates a comparison runner for GPT-image-2, SD3.5, and FLUX on the same three advertising cases.

The goal is not to make FLUX run by default. The goal is to make it safe to evaluate when a developer explicitly prepares the local model/dependencies and opts into heavy execution.

## Guard Policy

- `flux_local` and `flux_local_smoke` are disabled by default.
- FLUX only becomes eligible when `EASYADS_ENABLE_FLUX_LOCAL=true`.
- The engine lazy-imports `torch` and `diffusers` only after the guard passes.
- Missing optional dependencies are reported as `t2i_engine_unavailable`.
- Disabled execution returns a failed GenerationJob with `t2i_engine_not_enabled`.
- HF token values and local model paths are not exposed in job metadata or reports.

## Environment

```bash
EASYADS_ENABLE_FLUX_LOCAL=false
EASYADS_FLUX_MODEL_ID=black-forest-labs/FLUX.1-schnell
EASYADS_FLUX_LOCAL_PATH=
EASYADS_FLUX_DEVICE=auto
EASYADS_FLUX_NUM_INFERENCE_STEPS=4
EASYADS_FLUX_GUIDANCE_SCALE=0.0
```

## Manual Smoke

```bash
python scripts/smoke_generation_job_t2i.py --engine flux --dry-run
python scripts/smoke_generation_job_t2i.py --engine flux --prompt "premium cafe advertising background with clean blank negative space for later Korean copy overlay"
```

The non-dry-run command is still blocked unless the FLUX env guard and model/token readiness are present.

## Engine Comparison Runner

```bash
python scripts/run_t2i_engine_comparison.py --dry-run
python scripts/run_t2i_engine_comparison.py --engines gpt_image_2,sd35_large,flux --dry-run
python scripts/run_t2i_engine_comparison.py --engines flux --actual --confirm-heavy
python scripts/run_t2i_engine_comparison.py --engines gpt_image_2,flux --actual --confirm-cost --confirm-heavy
```

`--actual` does not bypass engine guards. GPT-image-2 additionally requires `--confirm-cost`; SD3.5 and FLUX require `--confirm-heavy`.

Reports are written to `data/logs/t2i_engine_comparison_v1_{timestamp}.json` and `.md`. Generated artifacts stay under `data/outputs/`. Neither directory is a commit target.

## Comparison Cases

- `cafe_dessert_001`
- `restaurant_bbq_001`
- `beauty_salon_001`

Each result records engine, case id, status, job id, runtime, final artifact path, public URL fields when available, error summary, prompt hash/preview, and manual quality review placeholders.

## Follow-up

1. Run actual FLUX local smoke only after GPU/VRAM/model/env readiness is confirmed.
2. Compare GPT-image-2, SD3.5, and FLUX outputs manually on quality, speed, cost, and operational complexity.
3. Decide generated result static serving or signed URL policy before exposing result URLs in production frontend UX.
