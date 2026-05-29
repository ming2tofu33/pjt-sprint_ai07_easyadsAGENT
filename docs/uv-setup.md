# UV Setup

This document is the standard local setup guide for EasyAds MVP development.

## 1. Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Check installation:

```powershell
uv --version
```

## 2. Move to the Project

```powershell
cd C:\Users\UserK\Downloads\easyads-local
```

## 3. Create the Virtual Environment

```powershell
uv venv
```

Activate it when you want a traditional shell workflow:

```powershell
.\.venv\Scripts\activate
```

Or run commands without activation:

```powershell
uv run python --version
```

## 4. Install Core and Development Dependencies

For backend, LangGraph, LLM skeleton, Vision MVP, mock T2I, and tests:

```powershell
uv pip sync requirements.txt requirements-dev.txt
```

`uv pip sync` makes the environment match the listed requirements. If you install GPU packages later, run the GPU commands after this sync step. Running `uv pip sync requirements.txt requirements-dev.txt` again may remove GPU-only packages because they are intentionally split out.

## 5. Verify the Environment

```powershell
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

The standard MVP verification is a full pytest pass. Vision/TLFP coverage is included in the test suite.

## 6. Optional T2I Candidate Check

The candidate check should not download or load local models unless explicitly requested:

```powershell
uv run python scripts\check_t2i_candidates.py
```

Use `--load-local` or `--generate-local` only after explicit approval because those paths may load large local models.

## 7. GPU Workers

General backend, LLM, Vision, and mock T2I work does not require GPU packages. Local SD3.5/FLUX workers should follow `docs/gpu-cu118-setup.md`.
