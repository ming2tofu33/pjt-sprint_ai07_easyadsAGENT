"""Dry-run and guarded actual comparison runner for T2I engines."""

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

BATCH_ID = "t2i_engine_comparison_v1"
ENGINE_RUN_MODES = {
    "gpt_image_2": "gpt_image_2_smoke",
    "sd35_large": "sd35_local_smoke",
    "flux": "flux_local_smoke",
}

CASES = [
    {
        "case_id": "cafe_dessert_001",
        "business_type": "cafe",
        "user_input": (
            "Create a premium cafe advertising background for a strawberry latte new menu. "
            "Do not include text, logos, signage, or watermarks. Leave clean blank negative "
            "space for later Korean copy overlay."
        ),
    },
    {
        "case_id": "restaurant_bbq_001",
        "business_type": "restaurant_bbq",
        "user_input": (
            "Create a premium Korean BBQ restaurant advertising background for dinner and "
            "group reservations. Do not include text, logos, signage, or watermarks. Leave "
            "clean blank negative space for later Korean copy overlay."
        ),
    },
    {
        "case_id": "beauty_salon_001",
        "business_type": "beauty_skincare",
        "user_input": (
            "Create a clean premium beauty salon advertising background for skincare "
            "consultation reservations. Do not include text, logos, signage, or watermarks. "
            "Leave clean blank negative space for later Korean copy overlay."
        ),
    },
]


def run_comparison(
    engines: list[str],
    dry_run: bool,
    actual: bool,
    confirm_cost: bool,
    confirm_heavy: bool,
    output_dir: Path,
) -> dict[str, Any]:
    started = perf_counter()
    report: dict[str, Any] = {
        "schema_version": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "actual": actual,
        "engines": engines,
        "engine_readiness": {engine: _engine_readiness(engine, confirm_cost, confirm_heavy) for engine in engines},
        "cases": [],
        "summary": {"total_cases": len(CASES), "total_results": 0, "total_success": 0, "total_blocked": 0, "total_failed": 0},
    }

    client = None if dry_run or not actual else TestClient(create_app())
    for engine in engines:
        readiness = report["engine_readiness"][engine]
        for case in CASES:
            result = _case_result_stub(engine, case)
            if dry_run:
                result["status"] = "dry_run"
                result["error_message"] = "Dry-run only; no engine execution attempted."
            elif not actual:
                result["status"] = "blocked"
                result["error_code"] = "actual_not_requested"
                result["error_message"] = "Pass --actual to attempt guarded execution."
            elif readiness["missing_requirements"]:
                result["status"] = "blocked"
                result["error_code"] = "missing_engine_requirements"
                result["error_message"] = ", ".join(readiness["missing_requirements"])
            else:
                result.update(_run_case(client, engine, case))
            report["cases"].append(result)

    report["summary"]["total_results"] = len(report["cases"])
    report["summary"]["total_success"] = sum(1 for case in report["cases"] if case["status"] == "done")
    report["summary"]["total_blocked"] = sum(1 for case in report["cases"] if case["status"] in {"blocked", "dry_run"})
    report["summary"]["total_failed"] = sum(1 for case in report["cases"] if case["status"] == "failed")
    report["total_runtime_ms"] = int((perf_counter() - started) * 1000)
    json_path, md_path = write_reports(report, output_dir)
    report["report_paths"] = {"json": json_path.as_posix(), "md": md_path.as_posix()}
    return report


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{BATCH_ID}_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    redacted = _redact(report)
    json_path.write_text(json.dumps(redacted, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(redacted), encoding="utf-8")
    return json_path, md_path


def _run_case(client: TestClient | None, engine: str, case: dict[str, str]) -> dict[str, Any]:
    if client is None:
        return {"status": "blocked", "error_code": "client_not_initialized"}

    started = perf_counter()

    response = client.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": case["user_input"],
            "run_mode": ENGINE_RUN_MODES[engine],
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
            "job_id": None,
            "latency_ms": None,
            "total_runtime_ms": int((perf_counter() - started) * 1000),
            "final_image_path": None,
            "final_image_url": None,
            "download_url": None,
            "error_code": "invalid_response",
            "error_message": response.text[:500],
            "model_source": None,
            "gpu_used": None,
            "image_exists": False,
        }

    job = payload.get("job") or {}
    result_payload = job.get("result_payload") or {}

    metadata_path = result_payload.get("metadata_path")
    metadata = _read_safe_metadata(metadata_path)
    engine_metadata = metadata.get("engine_metadata") or {}

    final_image_path = result_payload.get("final_image_path")
    error = job.get("error") or {}

    return {
        "status": job.get("status") or "failed",
        "job_id": job.get("job_id"),
        "latency_ms": metadata.get("latency_ms"),
        "total_runtime_ms": int((perf_counter() - started) * 1000),
        "final_image_path": final_image_path,
        "final_image_url": result_payload.get("final_image_url"),
        "download_url": result_payload.get("download_url"),
        "error_code": error.get("error_code"),
        "error_message": error.get("message"),
        "model_source": engine_metadata.get("model_source"),
        "gpu_used": engine_metadata.get("device") == "cuda" if "device" in engine_metadata else None,
        "image_exists": bool(final_image_path and Path(final_image_path).exists()),
    }


def _case_result_stub(engine: str, case: dict[str, str]) -> dict[str, Any]:
    return {
        "engine": engine,
        "case_id": case["case_id"],
        "business_type": case["business_type"],
        "status": "pending",
        "job_id": None,
        "latency_ms": None,
        "total_runtime_ms": None,
        "final_image_path": None,
        "final_image_url": None,
        "download_url": None,
        "error_code": None,
        "error_message": None,
        "model_source": None,
        "gpu_used": None,
        "prompt_hash": hashlib.sha256(case["user_input"].encode("utf-8")).hexdigest(),
        "prompt_preview": " ".join(case["user_input"].split())[:160],
        "image_exists": False,
        "manual_quality_score_placeholder": None,
        "manual_notes_placeholder": "",
    }


def _engine_readiness(engine: str, confirm_cost: bool, confirm_heavy: bool) -> dict[str, Any]:
    env = {
        "external_t2i_enabled": _env_bool("EASYADS_ENABLE_EXTERNAL_T2I"),
        "gpt_image_2_enabled": _env_bool("EASYADS_ENABLE_GPT_IMAGE_2"),
        "sd35_local_enabled": _env_bool("EASYADS_ENABLE_SD35_LOCAL"),
        "flux_local_enabled": _env_bool("EASYADS_ENABLE_FLUX_LOCAL"),
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "hf_token_present": bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")),
        "sd35_local_path_present": bool(os.getenv("EASYADS_SD35_LOCAL_PATH")),
        "flux_local_path_present": bool(os.getenv("EASYADS_FLUX_LOCAL_PATH")),
    }
    if engine == "gpt_image_2":
        checks = [
            ("--confirm-cost", confirm_cost),
            ("EASYADS_ENABLE_EXTERNAL_T2I", env["external_t2i_enabled"]),
            ("EASYADS_ENABLE_GPT_IMAGE_2", env["gpt_image_2_enabled"]),
            ("OPENAI_API_KEY", env["openai_api_key_present"]),
        ]
    elif engine == "sd35_large":
        checks = [
            ("--confirm-heavy", confirm_heavy),
            ("EASYADS_ENABLE_SD35_LOCAL", env["sd35_local_enabled"]),
            ("HF_TOKEN_or_EASYADS_SD35_LOCAL_PATH", env["hf_token_present"] or env["sd35_local_path_present"]),
        ]
    else:
        checks = [
            ("--confirm-heavy", confirm_heavy),
            ("EASYADS_ENABLE_FLUX_LOCAL", env["flux_local_enabled"]),
            ("HF_TOKEN_or_EASYADS_FLUX_LOCAL_PATH", env["hf_token_present"] or env["flux_local_path_present"]),
        ]
    missing = [name for name, present in checks if not present]
    return {"env": env, "missing_requirements": missing, "ready": not missing}


def _redact(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    for secret_name in ("OPENAI_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN"):
        secret = os.getenv(secret_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return json.loads(text)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# T2I Engine Comparison v1",
        "",
        "## Summary",
        "",
        f"- Dry run: `{report['dry_run']}`",
        f"- Actual: `{report['actual']}`",
        f"- Engines: `{', '.join(report['engines'])}`",
        f"- Total results: `{report['summary']['total_results']}`",
        f"- Success: `{report['summary']['total_success']}`",
        f"- Blocked/dry-run: `{report['summary']['total_blocked']}`",
        f"- Failed: `{report['summary']['total_failed']}`",
        "",
        "## Engine Readiness",
        "",
    ]
    for engine, readiness in report["engine_readiness"].items():
        missing = ", ".join(readiness["missing_requirements"]) or "none"
        lines.append(f"- `{engine}` ready=`{readiness['ready']}` missing=`{missing}`")
    lines.extend(["", "## Case Results", "", "| Engine | Case | Status | Job ID | Image Exists | Error |", "|---|---|---|---|---:|---|"])
    for case in report["cases"]:
        lines.append(
            f"| {case['engine']} | {case['case_id']} | {case['status']} | {case.get('job_id') or ''} | "
            f"{case.get('image_exists')} | {case.get('error_code') or ''} |"
        )
    lines.extend(["", "## Manual Review Placeholder", "", "| Engine | Case | Quality score | Notes |", "|---|---|---:|---|"])
    for case in report["cases"]:
        lines.append(f"| {case['engine']} | {case['case_id']} | TBD |  |")
    lines.append("")
    lines.append("Reports do not include raw API keys, HF tokens, base64 image data, or raw image bytes.")
    return "\n".join(lines)


def _env_bool(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _parse_engines(value: str) -> list[str]:
    engines = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(engines) - set(ENGINE_RUN_MODES))
    if unknown:
        raise ValueError(f"unknown engines: {', '.join(unknown)}")
    return engines

def _read_safe_metadata(metadata_path: str | None) -> dict[str, Any]:
    if not metadata_path:
        return {}

    path = Path(metadata_path)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engines", default="gpt_image_2,sd35_large,flux")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--actual", action="store_true")

    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument("--confirm-heavy", action="store_true")
    parser.add_argument("--output-dir", default="data/logs")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    engines = _parse_engines(args.engines)
    dry_run = args.dry_run or not args.actual
    report = run_comparison(
        engines=engines,
        dry_run=dry_run,
        actual=args.actual,
        confirm_cost=args.confirm_cost,
        confirm_heavy=args.confirm_heavy,
        output_dir=Path(args.output_dir),
    )
    print(json.dumps({"status": "ok", "report_paths": report["report_paths"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
