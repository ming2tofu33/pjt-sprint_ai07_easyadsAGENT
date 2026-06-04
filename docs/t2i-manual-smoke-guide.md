# T2I Manual Smoke Guide

This guide covers manual smoke reports for the guarded GenerationJob T2I lanes. The default CI and local test path must not call GPT-image-2, OpenAI APIs, SD3.5, FLUX, Hugging Face downloads, or GPU-heavy model loads.

## Dry Run

Dry run creates a readiness report only. It never calls an external API or local model.

```bash
python scripts/smoke_generation_job_t2i.py --engine gpt_image_2 --dry-run
python scripts/smoke_generation_job_t2i.py --engine sd35_large --dry-run
python scripts/smoke_generation_job_t2i.py --engine flux --dry-run
```

Reports are written to `data/logs/t2i_manual_smoke_{engine}_{timestamp}.json` and `.md`. `data/logs/` is a runtime directory and must not be committed.

## GPT-image-2 Actual Smoke

Actual smoke is allowed only when all requirements are already present in the shell environment:

```bash
EASYADS_ENABLE_EXTERNAL_T2I=true
EASYADS_ENABLE_GPT_IMAGE_2=true
OPENAI_API_KEY=<already configured in shell>
```

Run without putting the key in the command line:

```bash
python scripts/smoke_generation_job_t2i.py \
  --engine gpt_image_2 \
  --prompt "premium cafe strawberry latte advertising background with clean empty space for later Korean copy overlay"
```

If flags or credentials are missing, the script writes a `blocked` report and does not call the engine.

## SD3.5 Local Smoke

Actual SD3.5 smoke is allowed only when the local lane is explicitly enabled and the environment has a token or local model path plus required dependencies/model readiness:

```bash
EASYADS_ENABLE_SD35_LOCAL=true
HF_TOKEN=<already configured in shell>
# or EASYADS_SD35_LOCAL_PATH=<local model path>
```

Run without putting tokens in the command line:

```bash
python scripts/smoke_generation_job_t2i.py \
  --engine sd35_large \
  --prompt "premium Korean BBQ restaurant advertising background, warm lighting, clean reserved text area for later Korean copy overlay"
```

If env flags, dependency/model readiness, token, model path, or GPU readiness are missing, write a `blocked` or `failed` report and do not commit generated files.

## FLUX Local Smoke

Actual FLUX smoke is allowed only when the local lane is explicitly enabled and the environment has a token or local model path plus required dependencies/model readiness:

```bash
EASYADS_ENABLE_FLUX_LOCAL=true
HF_TOKEN=<already configured in shell>
# or EASYADS_FLUX_LOCAL_PATH=<local model path>
```

Run without putting tokens in the command line:

```bash
python scripts/smoke_generation_job_t2i.py \
  --engine flux \
  --prompt "premium cafe advertising background with clean blank negative space for later Korean copy overlay"
```

If env flags, dependency/model readiness, token, model path, or GPU readiness are missing, write a `blocked` or `failed` report and do not commit generated files.

## Report Safety

Reports include credential presence booleans, prompt hash/preview, job id, latency, safe result payload fields, output paths, and error summaries. Reports must not include raw API keys, HF tokens, base64 image data, or image bytes.

## GPT-image-2 Quality Batch

Use `scripts/run_gpt_image2_quality_batch.py` when the goal is manual advertising quality review rather than a simple engine smoke check.

```bash
python scripts/run_gpt_image2_quality_batch.py --dry-run
python scripts/run_gpt_image2_quality_batch.py --actual --max-cases 3 --confirm-cost
```

Actual quality batch requires `EASYADS_ENABLE_EXTERNAL_T2I=true`, `EASYADS_ENABLE_GPT_IMAGE_2=true`, `EASYADS_QUALITY_BATCH_CONFIRM=true`, and an existing `OPENAI_API_KEY` in the shell. The runner enforces one image per case and a hard cap of six cases. Reports are written to `data/logs/`; generated images are written to `data/outputs/`. Neither directory should be committed.

## T2I Engine Comparison

Use `scripts/run_t2i_engine_comparison.py` to compare GPT-image-2, SD3.5, and FLUX on the same cafe, restaurant BBQ, and beauty cases.

```bash
python scripts/run_t2i_engine_comparison.py --dry-run
python scripts/run_t2i_engine_comparison.py --engines gpt_image_2,sd35_large,flux --dry-run
python scripts/run_t2i_engine_comparison.py --engines flux --actual --confirm-heavy
python scripts/run_t2i_engine_comparison.py --engines gpt_image_2,flux --actual --confirm-cost --confirm-heavy
```

`--actual` is still guarded by each engine's environment flags and credentials/model readiness. GPT-image-2 requires `--confirm-cost`; SD3.5 and FLUX require `--confirm-heavy`. Reports are written under `data/logs/` and must not be committed.
