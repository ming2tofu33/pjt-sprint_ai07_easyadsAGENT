# T2I Candidate Check

This check validates whether the current machine can run the Week 2 text-to-image candidates without spending API budget or downloading large models by default.

## Candidates

- `gpt_image_2`: OpenAI image API fallback lane.
- `sd35_large`: local SD3.5 Large self-hosted lane.
- `flux`: local FLUX lane, intended for lazy/on-demand loading because it is heavy.

## Local RTX 3090 Setup

Recommended install order for the current local development machine:

```powershell
python -m pip install -r requirements.txt
python scripts/check_t2i_candidates.py
```

The current machine already has CUDA-enabled torch working, so this project does not pin or reinstall torch in `requirements.txt`. Reinstalling torch can easily replace the CUDA build with an incompatible CPU or wrong-CUDA build. Keep the existing CUDA torch unless a separate, explicit GPU environment task is planned.

Local T2I import dependencies are listed in `requirements.txt`:

- `diffusers==0.32.2`
- `transformers==4.46.3`
- `accelerate`
- `safetensors==0.7.0`
- `huggingface_hub`
- `sentencepiece`
- `protobuf`
- `openai`

## Environment Keys

Set `HF_TOKEN` and `OPENAI_API_KEY` in the process environment or local `.env`. Do not commit actual keys. `docs/api_key.env` is ignored as a safety backstop but is not loaded by the runtime config.

Example key names only:

```text
HF_TOKEN=
OPENAI_API_KEY=
```

## Default Dry Run

Run:

```powershell
python scripts/check_t2i_candidates.py
```

Default behavior:

- GPT-image-2 checks `OPENAI_API_KEY` presence and OpenAI SDK import only.
- SD3.5 checks Python/package versions, CUDA status, device name, VRAM, `HF_TOKEN`, and `StableDiffusion3Pipeline` import only.
- FLUX checks Python/package versions, CUDA status, device name, VRAM, `HF_TOKEN`, and `FluxPipeline` import only.
- No OpenAI API call is made.
- No Hugging Face model is downloaded.
- No local model is loaded.
- No image is generated.

Reports are written to:

- `data/logs/t2i_candidate_check.json`
- `data/logs/t2i_candidate_check.md`

Generated images, when explicitly enabled, are written under:

- `data/outputs/candidate_check/{timestamp}/`

## GPT-image-2

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
- Local T2I dependency list for import-level readiness.
- Tests for missing API key behavior and dry-run candidate checks.

## Not Implemented In This Step

- FastAPI endpoint integration.
- Streamlit integration.
- Default GPT-image-2 API invocation.
- Default SD3.5/FLUX download, load, or generation.
- Vision pipeline, inpainting, rembg/SAM, ControlNet, LoRA, or benchmark runs.


## GPT-image-2 Smoke Result - 2026-05-26

Command:

```powershell
python scripts/check_t2i_candidates.py --include-api --engines gpt_image_2
```

Result summary:

- `can_generate`: `true`
- `output_path`: `data/outputs/candidate_check/20260526_152827/gpt_image_2_0.png`
- saved_file_type: `png`
- `latency_ms`: `46167`
- `error`: `null`

This run made one explicit GPT-image-2 API call and may have incurred API cost. The API key value was not written to logs, docs, or reports. Generated files and candidate check logs remain ignored by git.

Next follow-up:

- Keep this as a connectivity/cost-guard smoke result, not as final image quality evidence.
- Use a separate benchmark step for quality comparison against SD3.5 and FLUX.
- If future API responses return URL-only output, add URL download-to-file handling without re-calling the API.

## SD3.5 Large Load-Local Retry Result - 2026-05-26

Commands:

```powershell
python scripts/check_t2i_candidates.py --engines sd35_large
python scripts/check_t2i_candidates.py --load-local --engines sd35_large
```

Retry context:

- Previous 6-A load failed because Hugging Face gated model authorization was missing for `stabilityai/stable-diffusion-3.5-large`.
- After access approval, the same load-local check was retried once.

Result summary:

- `can_import_pipeline`: `true`
- `hf_token_present`: `true`
- GPU: `NVIDIA GeForce RTX 3090`
- VRAM: `24GB`
- `can_load_model`: `true`
- `can_generate`: `false`
- `load_latency_ms`: `2062179`
- `cuda_oom`: `false`
- `cuda_memory_before`: `allocated=0.0GB, max_allocated=0.0GB, reserved=0.0GB`
- `cuda_memory_after`: `allocated=0.0GB, max_allocated=0.0GB, reserved=0.0GB`
- `error`: `null`

No `--generate-local` run was executed. This validated that the local environment can access and load `stabilityai/stable-diffusion-3.5-large`.

## SD3.5 Large Generation Smoke Result - 2026-05-27

Command:

```powershell
python scripts/check_t2i_candidates.py --load-local --generate-local --engines sd35_large
```

Run context:

- This run was performed after the 6-A load-local retry succeeded.
- The model files had already been downloaded/cached, so this was a warm-cache generation smoke.
- This is a local generation connectivity and memory smoke, not a final image quality evaluation.

Result summary:

- `can_import_pipeline`: `true`
- `hf_token_present`: `true`
- GPU: `NVIDIA GeForce RTX 3090`
- VRAM: `24GB`
- `can_load_model`: `true`
- `can_generate`: `true`
- `output_path`: `data/outputs/candidate_check/20260527_163310/sd35_large_0.png`
- saved_file_type: `png`
- file_size_bytes: `455115`
- `latency_ms`: `265285`
- smoke_settings: `num_images=1`, `num_inference_steps=4`, `torch_dtype=float16`, `use_safetensors=true`
- `cuda_oom`: `false`
- `cuda_memory_before_load`: `allocated=0.0GB, max_allocated=0.0GB, reserved=0.0GB`
- `cuda_memory_after_load`: `allocated=0.0GB, max_allocated=0.0GB, reserved=0.0GB`
- `cuda_memory_before_generate`: `allocated=27.98GB, max_allocated=27.98GB, reserved=28.04GB`
- `cuda_memory_after_generate`: `allocated=27.99GB, max_allocated=30.38GB, reserved=32.26GB`
- `error`: `null`

The generated image and candidate check logs remain ignored by git. Next follow-up: inspect the smoke image qualitatively, then decide whether to add a smaller/faster SD3.5 smoke profile or proceed to a real SD3.5 service engine wrapper.

Interpretation notes:

- The SD3.5 load and generation candidate validation is complete at smoke-test level: gated access works, local load works, and one local image was generated.
- CUDA memory stats above come from torch allocator metrics and should be treated as indicative, not definitive physical VRAM usage. A later profiling step should validate real GPU usage with `nvidia-smi` or a dedicated profiler.
- `latency_ms=265285` is acceptable for a one-off smoke check, but too slow for an operational default path. Future work should separate `smoke`, `fast preview`, and `balanced/default` profiles.
- Manual visual check found that the generated image was not suitable as an advertising background: it looked closer to a plain reddish desktop/background image than a useful commercial poster background.
- This result therefore proves local generation capability, not image quality readiness. Quality tuning should happen in a later benchmark/prompt-profile step.
