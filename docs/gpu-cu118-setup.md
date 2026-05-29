# GPU CUDA 11.8 Setup

This guide is for local image generation workers who handle SD3.5 Large, FLUX, or future diffusers-based inference.

General backend, LangGraph, LLM skeleton, Vision MVP, and mock T2I work should use `docs/uv-setup.md` and does not need this GPU layer.

## Target Users

- RTX 3090 or similar NVIDIA GPU users
- Local SD3.5 Large / FLUX / diffusers inference maintainers
- Workers explicitly approved to load or generate with local models

## Prerequisites

- NVIDIA driver installed
- Driver compatible with CUDA 11.8 PyTorch wheels
- `uv` installed
- `.venv` created with `uv venv`
- Core dependencies installed with the recommended lockfile workflow:

```powershell
uv sync --group dev
```

Compatibility workflow:

```powershell
uv pip sync requirements.txt requirements-dev.txt
```

The default `uv sync --group dev` path does not install torch or CUDA packages.

## Install PyTorch CUDA 11.8

Install torch separately so the CUDA wheel index is explicit:

```powershell
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

The previously verified local baseline was `torch 2.6.0+cu118`. Team members may use a newer compatible CUDA 11.8 wheel if driver and project tests pass.

## Install Local T2I Dependencies

```powershell
uv pip install -r requirements-gpu-cu118.txt
```

`requirements-gpu-cu118.txt` intentionally excludes torch so PyTorch can be installed from the CUDA wheel index above.

If you want to use the optional dependency group from `pyproject.toml`, install torch first, then run:

```powershell
uv pip install -e ".[gpu-cu118]"
```

Torch remains a separate install because CUDA wheel index selection is environment-specific.

Do not use `uv sync --extra gpu-cu118` as the standard GPU setup path yet. Until the torch CUDA index policy is finalized, it may resolve an unintended CPU torch wheel or create a lock strategy mismatch.

## Check CUDA

```powershell
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Expected output:

- torch version
- `True` for `torch.cuda.is_available()`
- GPU name, for example `NVIDIA GeForce RTX 3090`

## T2I Candidate Check

Dry-run candidate inspection:

```powershell
uv run python scripts\check_t2i_candidates.py --engines sd35_large
```

Do not use model-loading flags without explicit approval:

- `--load-local`
- `--generate-local`

Some Hugging Face models may require account access and `HF_TOKEN`.

## Do Not Commit

- generated images
- `data/outputs/`
- `data/logs/`
- `data/processed/`
- `data/uploads/`
- model cache
- `.env`
- `docs/api_key.env`
- model weights or safetensors
