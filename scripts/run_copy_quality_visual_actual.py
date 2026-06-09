"""Guarded visual actual verification for Copy Quality Core v2."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CASES = ("cafe_dessert_001", "restaurant_bbq_001", "beauty_salon_001")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument("--output-dir", default="data/outputs/copy_quality_visual_actual_v2")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"copy_quality_visual_actual_v2_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    if report["status"] == "blocked":
        return 2
    return 0


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    missing = missing_actual_requirements(args)
    runs = [
        {
            "case_id": case_id,
            "status": "blocked" if args.actual and missing else "dry_run",
            "flux2_klein_actual_image_generation": False,
            "openai_vlm_actual_final_judge": False,
            "missing_requirements": missing if args.actual else [],
            "quality": None,
            "copy_safe_area": None,
            "fake_text_logo_risk": None,
            "business_fit": None,
            "mobile_qa_fit": None,
            "notes": None,
        }
        for case_id in CASES[: max(1, args.max_cases)]
    ]
    return {
        "schema_version": "copy_quality_visual_actual_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "blocked" if args.actual and missing else "dry_run",
        "actual_requested": args.actual,
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "hf_token_present": bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")),
        "runs": runs,
    }


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    if not args.actual:
        return []
    missing: list[str] = []
    if os.getenv("EASYADS_COPY_QUALITY_ACTUAL") != "1":
        missing.append("EASYADS_COPY_QUALITY_ACTUAL=1")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if os.getenv("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL") != "true":
        missing.append("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true")
    if not (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")):
        missing.append("HF_TOKEN_or_HUGGINGFACE_TOKEN")
    try:
        module = importlib.import_module("diffusers")
        if not hasattr(module, "Flux2KleinPipeline"):
            missing.append("diffusers.Flux2KleinPipeline")
    except Exception:
        missing.append("diffusers")
    return missing


if __name__ == "__main__":
    raise SystemExit(main())
