# UV Migration Plan

The project now includes `pyproject.toml`, `uv.lock`, and `.python-version` as the primary uv project setup. Requirements files remain as a compatibility path for teammates who still use `uv pip sync`.

## Current Stage

- `pyproject.toml` defines runtime dependencies, the `dev` dependency group, and the `gpu-cu118` optional dependency set.
- `uv.lock` is committed for reproducible default and dev sync.
- `.python-version` records the recommended Python major/minor version.
- `requirements.txt`, `requirements-dev.txt`, and `requirements-gpu-cu118.txt` remain available for compatibility.
- GPU/CUDA packages are not installed by default.
- Torch CUDA installation remains a separate documented command.

## Recommended Workflow

```powershell
uv venv
uv sync --group dev
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

## Compatibility Workflow

```powershell
uv venv
uv pip sync requirements.txt requirements-dev.txt
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

## Next Stage

- stabilize dependency groups across developer machines
- decide CI command set
- decide GPU optional dependency and torch/CUDA lock strategy
- test Windows and Linux uv sync behavior
- consider whether GPU workers should use requirements or optional extras by default

## Migration Risks

- torch/CUDA wheels require explicit index handling
- Windows and Linux may need separate GPU installation notes
- optional GPU dependency groups need careful testing
- requirements files and `pyproject.toml` must stay aligned while both workflows exist

## Not Done in This Step

- no CI conversion
- no uv workspace setup
- no Dockerfile changes
- no automatic GPU package install
- no model download or local model load
