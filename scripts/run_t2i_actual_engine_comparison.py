"""Guarded actual T2I engine comparison runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.app.api.app import create_app  # noqa: E402
from orchestrator.app.db import settings as db_settings  # noqa: E402
from orchestrator.app.modal import settings as modal_settings  # noqa: E402
from orchestrator.app.storage import settings as storage_settings  # noqa: E402
from orchestrator.app.t2i.engine_policy import (  # noqa: E402
    get_image_engine_policy,
    resolve_requested_engines_for_plan,
)
from orchestrator.app.t2i.settings import load_t2i_settings  # noqa: E402

BATCH_ID = "t2i_actual_engine_comparison_v1"
ENGINE_RUN_MODES = {
    "gpt_image_2": "gpt_image_2_actual",
    "sd35_large": "sd35_local",
    "flux": "flux_local",
}
SMOKE_RUN_MODES = {
    "gpt_image_2": "gpt_image_2_smoke",
    "sd35_large": "sd35_local_smoke",
    "flux": "flux_local_smoke",
}
SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "EASYADS_R2_ACCESS_KEY_ID",
    "EASYADS_R2_SECRET_ACCESS_KEY",
)

CASES = [
    {
        "case_id": "cafe_dessert_001",
        "business_type": "cafe",
        "user_input": (
            "Create a premium cafe advertising background for a strawberry latte launch. "
            "Keep clean blank negative space for later Korean copy overlay. Do not include text, logos, or signage."
        ),
        "ad_format": "instagram_feed",
        "copy_generation_mode": "auto_pilot",
    },
    {
        "case_id": "restaurant_bbq_001",
        "business_type": "restaurant_bbq",
        "user_input": (
            "Create a premium Korean BBQ restaurant advertising background for dinner reservations. "
            "Use warm lighting and appetizing grill atmosphere with clean blank negative space. Do not include text."
        ),
        "ad_format": "instagram_feed",
        "copy_generation_mode": "auto_pilot",
    },
    {
        "case_id": "beauty_salon_001",
        "business_type": "beauty",
        "user_input": (
            "Create a clean premium beauty care advertising background with elegant white space for copy overlay. "
            "Avoid visible text, labels, logos, signage, or watermarks."
        ),
        "ad_format": "instagram_feed",
        "copy_generation_mode": "auto_pilot",
    },
]


def run_comparison(
    *,
    plan: str,
    requested_engines: list[str] | None,
    case_ids: list[str] | None,
    max_cases: int,
    dry_run: bool,
    confirm_actual: bool,
    execution_backend: str,
    require_db_r2: bool,
    include_comparison: bool,
    output_json: Path | None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    policy = get_image_engine_policy(plan)
    resolved_engines = resolve_requested_engines_for_plan(
        plan=plan,
        requested_engines=requested_engines,
        include_comparison=include_comparison,
    )
    cases = _resolve_cases(case_ids, max_cases)
    actual_generation = bool(confirm_actual and not dry_run)
    readiness = {
        engine: _engine_readiness(engine, execution_backend=execution_backend, require_db_r2=require_db_r2)
        for engine in resolved_engines
    }
    runs = []
    client = TestClient(create_app()) if actual_generation and any(item["ready"] for item in readiness.values()) else None

    for case in cases:
        for engine in resolved_engines:
            run = _run_stub(case, engine, use_actual_run_mode=actual_generation)
            engine_ready = readiness[engine]
            if dry_run:
                run["status"] = "dry_run"
                run["error_message"] = "Dry-run only; no engine execution attempted."
            elif not confirm_actual:
                run["status"] = "blocked"
                run["error_code"] = "actual_not_confirmed"
                run["error_message"] = "Pass --confirm-actual to attempt guarded actual generation."
            elif not engine_ready["ready"]:
                run["status"] = "blocked"
                run["error_code"] = "engine_not_ready"
                run["error_message"] = ", ".join(engine_ready["missing_requirements"])
            else:
                run.update(_execute_case(client, case, engine))
            runs.append(run)

    finished_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "schema_version": BATCH_ID,
        "status": _report_status(runs, dry_run=dry_run),
        "plan": policy.plan,
        "policy": policy.model_dump(mode="json"),
        "requested_engines": requested_engines or [],
        "resolved_engines": resolved_engines,
        "actual_generation": actual_generation,
        "execution_backend": execution_backend,
        "require_db_r2": require_db_r2,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_runtime_ms": int((perf_counter() - started) * 1000),
        "summary": _summary(runs, cases),
        "readiness": readiness,
        "runs": runs,
    }
    report_path = write_report(report, output_json)
    report["report_path"] = report_path.as_posix()
    return report


def write_report(report: dict[str, Any], output_json: Path | None = None) -> Path:
    if output_json is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_json = Path("data/logs") / f"{BATCH_ID}_{timestamp}.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)

    report_to_save = {**report, "report_path": output_json.as_posix()}
    output_json.write_text(json.dumps(_redact(report_to_save), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_json


def _execute_case(client: TestClient | None, case: dict[str, str], engine: str) -> dict[str, Any]:
    if client is None:
        return {"status": "blocked", "error_code": "client_not_initialized"}
    started = perf_counter()
    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": case["user_input"],
            "run_mode": ENGINE_RUN_MODES[engine],
            "ad_format": case["ad_format"],
            "copy_generation_mode": case["copy_generation_mode"],
            "metadata": {
                "comparison_batch_id": BATCH_ID,
                "case_id": case["case_id"],
                "business_type": case["business_type"],
            },
        },
    )
    try:
        payload = response.json()
    except Exception:
        return {
            "status": "failed",
            "total_runtime_ms": int((perf_counter() - started) * 1000),
            "error_code": "invalid_response",
            "error_message": response.text[:300],
        }
    job = payload.get("job") or {}
    result_payload = job.get("result_payload") or {}
    error = job.get("error") or {}
    metadata = job.get("metadata") or {}
    return {
        "status": "success" if job.get("status") == "done" else str(job.get("status") or "failed"),
        "job_id": job.get("job_id"),
        "total_runtime_ms": int((perf_counter() - started) * 1000),
        "output_path": job.get("output_path"),
        "final_image_path": result_payload.get("final_image_path"),
        "final_image_url_present": bool(result_payload.get("final_image_url")),
        "download_url_present": bool(result_payload.get("download_url")),
        "storage_provider": result_payload.get("storage_provider"),
        "object_key_present": bool(result_payload.get("object_key")),
        "error_code": error.get("error_code"),
        "error_type": error.get("error_type"),
        "error_message": _sanitize_error_message(error.get("message")),
        "error_detail": _sanitize_error_message(error.get("detail")),
        "clip_token_count": metadata.get("clip_token_count"),
        "clip_max_tokens": metadata.get("clip_max_tokens"),
        "clip_truncated": metadata.get("clip_truncated"),
        "prompt_2_used": metadata.get("prompt_2_used"),
        "critical_constraints_preserved": metadata.get("critical_constraints_preserved"),
    }


def _run_stub(case: dict[str, str], engine: str, *, use_actual_run_mode: bool) -> dict[str, Any]:
    run_mode = ENGINE_RUN_MODES[engine] if use_actual_run_mode else SMOKE_RUN_MODES[engine]
    return {
        "case_id": case["case_id"],
        "business_type": case["business_type"],
        "engine": engine,
        "run_mode": run_mode,
        "status": "pending",
        "job_id": None,
        "latency_ms": None,
        "total_runtime_ms": None,
        "output_path": None,
        "final_image_path": None,
        "final_image_url_present": False,
        "download_url_present": False,
        "storage_provider": None,
        "object_key_present": False,
        "error_code": None,
        "error_type": None,
        "error_message": None,
        "error_detail": None,
        "clip_token_count": None,
        "clip_max_tokens": None,
        "clip_truncated": None,
        "prompt_2_used": None,
        "critical_constraints_preserved": None,
        "prompt_hash": hashlib.sha256(case["user_input"].encode("utf-8")).hexdigest(),
        "prompt_preview": " ".join(case["user_input"].split())[:180],
        "manual_review_required": True,
        "manual_review": {
            "quality": None,
            "copy_safe_area": None,
            "fake_text_logo_risk": None,
            "business_fit": None,
            "mobile_qa_fit": None,
            "notes": None,
        },
    }

def _effective_execution_backend(execution_backend: str) -> str:
    if execution_backend == "auto":
        if modal_settings.get_t2i_execution_backend() == "modal":
            return "modal"
        return "local"
    return execution_backend

def _extend_modal_readiness(missing: list[str]) -> None:
    modal = modal_settings.get_modal_readiness()
    missing.extend(f"modal:{item}" for item in modal["missing_requirements"])
    if not modal["enabled"]:
        missing.append("EASYADS_ENABLE_MODAL_EXECUTION")
    if db_settings.get_db_backend() != "postgres":
        missing.append("EASYADS_DB_BACKEND=postgres")

def _engine_readiness(engine: str, *, execution_backend: str, require_db_r2: bool) -> dict[str, Any]:
    effective_backend = _effective_execution_backend(execution_backend)
    settings = load_t2i_settings()
    missing = []
    if engine == "gpt_image_2":
        if not settings.enable_external_t2i:
            missing.append("EASYADS_ENABLE_EXTERNAL_T2I")
        if not settings.enable_gpt_image_2:
            missing.append("EASYADS_ENABLE_GPT_IMAGE_2")
        if not settings.openai_api_key_present:
            missing.append("OPENAI_API_KEY")
    elif engine == "sd35_large":
        if effective_backend == "modal":
            _extend_modal_readiness(missing)
        else:
            if not settings.enable_sd35_local:
                missing.append("EASYADS_ENABLE_SD35_LOCAL")
            if not (settings.hf_token_present or settings.sd35_local_path):
                missing.append("HF_TOKEN_or_EASYADS_SD35_LOCAL_PATH")

    elif engine == "flux":
        if effective_backend == "modal":
            _extend_modal_readiness(missing)
        else:
            if not settings.enable_flux_local:
                missing.append("EASYADS_ENABLE_FLUX_LOCAL")
            if not (settings.hf_token_present or settings.flux_local_path):
                missing.append("HF_TOKEN_or_EASYADS_FLUX_LOCAL_PATH")
    else:
        missing.append("known_engine")

    if effective_backend == "modal" and engine in {"sd35_large", "flux"}:
        modal = modal_settings.get_modal_readiness()
        missing.extend(f"modal:{item}" for item in modal["missing_requirements"])
        if not modal["enabled"]:
            missing.append("EASYADS_ENABLE_MODAL_EXECUTION")
        if db_settings.get_db_backend() != "postgres":
            missing.append("EASYADS_DB_BACKEND=postgres")

    if require_db_r2:
        if db_settings.get_db_backend() != "postgres":
            missing.append("EASYADS_DB_BACKEND=postgres")
        r2 = storage_settings.get_r2_readiness()
        if not r2["enabled"]:
            missing.append("EASYADS_ENABLE_R2_UPLOAD_or_EASYADS_ASSET_STORAGE_BACKEND=r2")
        missing.extend(f"r2:{item}" for item in r2["missing_requirements"])

    return {
        "ready": not missing,
        "missing_requirements": _dedupe(missing),
        "secrets_present": {
            "openai_api_key": settings.openai_api_key_present,
            "hf_token": settings.hf_token_present,
            "modal_token_id": bool(os.getenv("MODAL_TOKEN_ID")),
            "modal_token_secret": bool(os.getenv("MODAL_TOKEN_SECRET")),
        },
    }


def _resolve_cases(case_ids: list[str] | None, max_cases: int) -> list[dict[str, str]]:
    selected = CASES
    if case_ids:
        allowed = set(case_ids)
        selected = [case for case in CASES if case["case_id"] in allowed]
    return selected[: max(1, max_cases)]

_PENDING_STATUSES = {"queued", "running", "submitted", "pending"}

def _report_status(runs: list[dict[str, Any]], *, dry_run: bool) -> str:
    if dry_run:
        return "dry_run"
    if not runs or all(run["status"] == "blocked" for run in runs):
        return "blocked"
    if all(run["status"] == "success" for run in runs):
        return "completed"
    if any(run["status"] == "success" for run in runs):
        return "partial"
    if any(run["status"] in _PENDING_STATUSES for run in runs):
        return "partial"
    return "failed"


def _summary(runs: list[dict[str, Any]], cases: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total_cases": len(cases),
        "total_runs": len(runs),
        "success": sum(1 for run in runs if run["status"] == "success"),
        "failed": sum(1 for run in runs if run["status"] == "failed"),
        "blocked": sum(1 for run in runs if run["status"] == "blocked"),
        "dry_run": sum(1 for run in runs if run["status"] == "dry_run"),
        "pending": sum(1 for run in runs if run["status"] in _PENDING_STATUSES),
    }


def _redact(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    for name in SECRET_ENV_NAMES:
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return json.loads(text)


def _dedupe(values: list[str]) -> list[str]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def _sanitize_error_message(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    for name in SECRET_ENV_NAMES:
        secret = os.getenv(name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return " ".join(text.split())[:500]


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-actual", action="store_true")
    parser.add_argument("--plan", default="free", choices=["free", "economic", "premium"])
    parser.add_argument("--engines", default=None)
    parser.add_argument("--cases", default=None)
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument("--execution-backend", default="auto", choices=["local", "modal", "auto"])
    parser.add_argument("--require-db-r2", action="store_true")
    parser.add_argument("--include-comparison", action="store_true")
    parser.add_argument("--output-json", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dry_run = args.dry_run or not args.confirm_actual
    report = run_comparison(
        plan=args.plan,
        requested_engines=_parse_csv(args.engines),
        case_ids=_parse_csv(args.cases),
        max_cases=args.max_cases,
        dry_run=dry_run,
        confirm_actual=args.confirm_actual,
        execution_backend=args.execution_backend,
        require_db_r2=args.require_db_r2,
        include_comparison=args.include_comparison,
        output_json=Path(args.output_json) if args.output_json else None,
    )
    safe_runs = [
        {
            "engine": run.get("engine"),
            "case_id": run.get("case_id"),
            "status": run.get("status"),
            "error_code": run.get("error_code"),
            "error_type": run.get("error_type"),
            "error_message": run.get("error_message"),
            "clip_token_count": run.get("clip_token_count"),
            "clip_max_tokens": run.get("clip_max_tokens"),
            "clip_truncated": run.get("clip_truncated"),
            "prompt_2_used": run.get("prompt_2_used"),
            "critical_constraints_preserved": run.get("critical_constraints_preserved"),
        }
        for run in report["runs"]
    ]
    print(
        json.dumps(
            {"status": report["status"], "report_path": report["report_path"], "runs": safe_runs},
            ensure_ascii=False,
        )
    )
    if report["status"] in {"failed", "blocked"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
