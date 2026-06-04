from __future__ import annotations

import os
import builtins

import orchestrator.app.t2i.settings as t2i_settings

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests


def test_flux_enabled_without_token_or_local_path_does_not_load_model(monkeypatch):
    reset_generation_job_store_for_tests()

    def env_only(name: str, default: str = "") -> str:
        return os.getenv(name, default)

    monkeypatch.setattr(t2i_settings, "_get_env", env_only)

    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "true")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.delenv("EASYADS_FLUX_LOCAL_PATH", raising=False)

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"diffusers", "torch"}:
            raise AssertionError(f"{name} should not be imported without token/local path readiness")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="flux_local_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "flux")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "t2i_engine_unavailable"
    assert "HF_TOKEN" in (failed.error.detail or failed.error.message or "")