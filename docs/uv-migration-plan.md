# UV Migration Plan

This repository currently uses requirements files with uv for reproducible local setup. We are not moving to `pyproject.toml` or `uv.lock` in this step.

## Current Stage

- Keep requirements-based installs.
- Use `uv venv`.
- Use `uv pip sync requirements.txt requirements-dev.txt`.
- Split GPU/local inference dependencies from the default backend environment.
- Preserve compatibility with existing pip/venv workflows while standardizing commands around uv.

## Next Stage

After the LangGraph, LLM, Vision, and T2I branches stabilize:

- introduce `pyproject.toml`
- define runtime, dev, and optional GPU dependency groups
- generate `uv.lock`
- use `uv sync`
- standardize `uv run` commands for development and CI

## Preconditions

- LangGraph/LLM/Vision/T2I changes merged and stable
- requirements split validated by the team
- GPU dependency policy confirmed
- shared pytest command stable
- all active developers can run the test suite from uv environments
- CI strategy agreed

## Migration Risks

- torch/CUDA wheels require explicit index handling
- Windows and Linux may need separate GPU installation notes
- optional GPU dependency groups need careful testing
- dev dependency groups should stay minimal
- team must decide whether `uv.lock` is committed

## Not Done in This Step

- no `pyproject.toml`
- no `uv.lock`
- no uv workspace setup
- no CI conversion
- no dependency group migration
