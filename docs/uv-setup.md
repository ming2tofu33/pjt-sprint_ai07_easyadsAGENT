# UV Setup

This document is the standard local setup guide for EasyAds MVP development.

The project now supports two uv workflows:

- Recommended: `pyproject.toml + uv.lock` with `uv sync --group dev`.
- Compatibility: requirements files with `uv pip sync requirements.txt requirements-dev.txt`.

Both workflows must keep the backend, LangGraph, LLM skeleton, Vision MVP, mock T2I, and tests working.

## 1. Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Linux/macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Check installation:

```powershell
uv --version
```

## 2. Python Version

Use the Python major/minor version in `.python-version`. It records the Python version used for the passing test environment.

## 3. Move to the Project

```powershell
cd C:\Users\UserK\Downloads\easyads-local
```

## 4. Create the Virtual Environment

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

## 5. Recommended Sync: pyproject + uv.lock

Use this path for new setup:

```powershell
uv sync --group dev
```

Then verify:

```powershell
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

## 6. Compatibility Sync: requirements

Use this path if a teammate still follows the requirements-based workflow:

```powershell
uv pip sync requirements.txt requirements-dev.txt
```

Then verify:

```powershell
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

`uv pip sync` makes the environment match the listed requirements. If you install GPU packages later, run the GPU commands after this sync step. Running `uv pip sync requirements.txt requirements-dev.txt` again may remove GPU-only packages because they are intentionally split out.

## 7. Optional T2I Candidate Check

The candidate check should not download or load local models unless explicitly requested:

```powershell
uv run python scripts\check_t2i_candidates.py
```

Use `--load-local` or `--generate-local` only after explicit approval because those paths may load large local models.

## 8. GPU Workers

General backend, LLM, Vision, and mock T2I work does not require GPU packages. Local SD3.5/FLUX workers should follow `docs/gpu-cu118-setup.md`.
