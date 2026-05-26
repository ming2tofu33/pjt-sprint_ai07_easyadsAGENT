# T2I Candidate Check

This check validates whether the current machine can run the Week 2 text-to-image candidates without spending API budget or downloading large models by default.

## Candidates

- `gpt_image_2`: OpenAI image API fallback lane.
- `sd35_large`: local SD3.5 Large self-hosted lane.
- `flux`: local FLUX lane, intended for lazy/on-demand loading because it is heavy.

## Default Dry Run

Run:

```powershell
python scripts/check_t2i_candidates.py
```

Default behavior:

- GPT-image-2 checks `OPENAI_API_KEY` presence and OpenAI SDK import only.
- SD3.5 checks Python package imports, CUDA status, device name, VRAM, `HF_TOKEN`, and `StableDiffusion3Pipeline` import only.
- FLUX checks Python package imports, CUDA status, device name, VRAM, `HF_TOKEN`, and `FluxPipeline` import only.
- No OpenAI API call is made.
- No Hugging Face model is downloaded.
- No local model is loaded.

Reports are written to:

- `data/logs/t2i_candidate_check.json`
- `data/logs/t2i_candidate_check.md`

Generated images, when explicitly enabled, are written under:

- `data/outputs/candidate_check/{timestamp}/`

## GPT-image-2

Set `OPENAI_API_KEY` in a local ignored environment file or process environment. Do not commit actual keys. This repository also supports an ignored local key file at `docs/api_key.env` for development machines.

Actual GPT-image-2 smoke generation is opt-in only:

```powershell
python scripts/check_t2i_candidates.py --include-api --engines gpt_image_2
```

This may spend API credit. The smoke path uses one simple restaurant poster-background prompt and one image. API failures are captured in the result report instead of crashing the script.

## SD3.5 Large Local

Default model id:

```text
stabilityai/stable-diffusion-3.5-large
```

Set `HF_TOKEN` before load/generate checks if the model requires gated access. Local RTX 3090 validation is preferred because it has better practical VRAM headroom for model development than the current GCP L4 setup. GCP L4 can still be used later for deployment, shared testing, and long-running jobs, but model load failures are more likely there.

Optional checks:

```powershell
python scripts/check_t2i_candidates.py --load-local --engines sd35_large
python scripts/check_t2i_candidates.py --load-local --generate-local --engines sd35_large
```

## FLUX Local

Default model id:

```text
black-forest-labs/FLUX.1-schnell
```

`black-forest-labs/FLUX.1-dev` remains a candidate, but the current config default is `FLUX.1-schnell`. FLUX should stay lazy-loaded/on-demand rather than resident at service startup.

Optional checks:

```powershell
python scripts/check_t2i_candidates.py --load-local --engines flux
python scripts/check_t2i_candidates.py --load-local --generate-local --engines flux
```

## Implemented Now

- Cost-safe `GPTImage2Engine` skeleton.
- Router support for `gpt_image_2` engine lookup and health.
- Dry-run candidate check script for GPT-image-2, SD3.5 Large, and FLUX.
- JSON and Markdown candidate reports.
- Tests for missing API key behavior and dry-run candidate checks.

## Not Implemented In This Step

- FastAPI endpoint integration.
- Streamlit integration.
- Default GPT-image-2 API invocation.
- Default SD3.5/FLUX download, load, or generation.
- Vision pipeline, inpainting, rembg/SAM, ControlNet, LoRA, or benchmark runs.
