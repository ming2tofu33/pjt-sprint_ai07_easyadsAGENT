"""Manual smoke report helper for guarded GenerationJob T2I lanes."""

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


RUN_MODE_BY_ENGINE = {
    "gpt_image_2": "gpt_image_2_smoke",
    "sd35_large": "sd35_local_smoke",
}


def build_env_summary(engine: str) -> dict[str, bool]:
    return {
        "external_t2i_enabled": _env_bool("EASYADS_ENABLE_EXTERNAL_T2I"),
        "engine_enabled": _env_bool("EASYADS_ENABLE_GPT_IMAGE_2") if engine == "gpt_image_2" else _env_bool("EASYADS_ENABLE_SD35_LOCAL"),
        "api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "hf_token_present": bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")),
        "sd35_local_path_present": bool(os.getenv("EASYADS_SD35_LOCAL_PATH")),
    }


def missing_requirements(engine: str, env: dict[str, bool]) -> list[str]:
    if engine == "gpt_image_2":
        checks = [
            ("EASYADS_ENABLE_EXTERNAL_T2I", env["external_t2i_enabled"]),
            ("EASYADS_ENABLE_GPT_IMAGE_2", env["engine_enabled"]),
            ("OPENAI_API_KEY", env["api_key_present"]),
        ]
    else:
        checks = [
            ("EASYADS_ENABLE_SD35_LOCAL", env["engine_enabled"]),
            ("HF_TOKEN_or_EASYADS_SD35_LOCAL_PATH", env["hf_token_present"] or env["sd35_local_path_present"]),
        ]
    return [name for name, present in checks if not present]


def run_smoke(engine: str, prompt: str, dry_run: bool, output_dir: Path, job_run_mode: str | None = None) -> dict[str, Any]:
    started = perf_counter()
    run_mode = job_run_mode or RUN_MODE_BY_ENGINE[engine]
    env = build_env_summary(engine)
    missing = missing_requirements(engine, env)
    status = "dry_run" if dry_run else "blocked" if missing else "failed"
    report: dict[str, Any] = {
        "schema_version": "t2i_manual_smoke_report_v1",
        "engine": engine,
        "run_mode": run_mode,
        "status": status,
        "job_id": None,
        "latency_ms": None,
        "output_paths": [],
        "result_payload": {},
        "env": env,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_preview": " ".join(prompt.split())[:120],
        "would_call_actual_engine": False,
        "missing_requirements": missing,
        "expected_outcome": "no actual call; readiness report only" if dry_run else ("blocked until requirements are met" if missing else "actual smoke through GenerationJob API"),
        "errors": [],
        "notes": [],
    }
    if dry_run:
        report["notes"].append(f"{engine} actual smoke not executed because dry-run was requested.")
        return _finish(report, started, output_dir)
    if missing:
        report["notes"].append(f"{engine} actual smoke not executed because env flags or credentials were not present.")
        return _finish(report, started, output_dir)

    report["would_call_actual_engine"] = True
    client = TestClient(create_app())
    response = client.post("/api/v1/generation-jobs", json={"user_input": prompt, "run_mode": run_mode})
    payload = response.json()
    job = payload.get("job") or {}
    report["job_id"] = job.get("job_id")
    report["status"] = "success" if response.status_code < 400 and job.get("status") == "done" else "failed"
    report["result_payload"] = job.get("result_payload") or {}
    report["output_paths"] = [value for key, value in (job.get("result_payload") or {}).items() if key.endswith("_path") and isinstance(value, str)]
    if job.get("error"):
        report["errors"].append(job["error"])
    return _finish(report, started, output_dir)


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"t2i_manual_smoke_{report['engine']}_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(_redact(report), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(_redact(report)), encoding="utf-8")
    return json_path, md_path


def _finish(report: dict[str, Any], started: float, output_dir: Path) -> dict[str, Any]:
    report["latency_ms"] = int((perf_counter() - started) * 1000)
    json_path, md_path = write_reports(report, output_dir)
    report["report_paths"] = {"json": json_path.as_posix(), "md": md_path.as_posix()}
    return report


def _redact(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    for secret_name in ("OPENAI_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN"):
        secret = os.getenv(secret_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return json.loads(text)


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# T2I Manual Smoke Report",
            "",
            f"- Engine: `{report['engine']}`",
            f"- Run mode: `{report['run_mode']}`",
            f"- Status: `{report['status']}`",
            f"- Job ID: `{report.get('job_id')}`",
            f"- Latency ms: `{report.get('latency_ms')}`",
            f"- Missing requirements: `{', '.join(report.get('missing_requirements') or []) or 'none'}`",
            f"- Output paths: `{len(report.get('output_paths') or [])}`",
            "",
            "No API key, HF token, base64 image data, or raw image bytes are stored in this report.",
        ]
    )


def _env_bool(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=sorted(RUN_MODE_BY_ENGINE), required=True)
    parser.add_argument("--prompt", default="카페 딸기라떼 광고 배경")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default="data/logs")
    parser.add_argument("--job-run-mode", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_smoke(args.engine, args.prompt, args.dry_run, Path(args.output_dir), args.job_run_mode)
    print(json.dumps({"status": report["status"], "report_paths": report["report_paths"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
