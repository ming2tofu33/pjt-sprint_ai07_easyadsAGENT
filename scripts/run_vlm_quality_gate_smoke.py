"""One-case FLUX.2 Klein + VLM quality gate smoke runner.

Default behavior is safe: no Modal call, no repeated retries. If prerequisites
are missing, writes a blocked JSON report under data/outputs.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.app.quality_gate.schemas import VLMQualityRequest
from orchestrator.app.quality_gate.service import deterministic_gate
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.flux2_klein import FLUX2_KLEIN_ENGINE
from orchestrator.app.t2i.settings import get_hf_token, load_t2i_settings


OUTPUT_DIR = Path("data/outputs/vlm_quality_gate_smoke")


def main() -> int:
    args = _parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "run_id": f"vlm_smoke_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "executed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "image_engine": args.engine,
        "image_backend": args.backend,
        "image_model": load_t2i_settings().flux2_klein_model_id,
        "width": 1024,
        "height": 1024,
        "local_vlm_provider": "deterministic",
        "local_vlm_model": "rule_based_v1",
        "api_vlm_provider": None,
        "api_vlm_model": None,
        "background_decision": None,
        "final_decision": None,
        "ocr_detected_spans": [],
        "fake_text": None,
        "watermark": None,
        "copy_safe_area": None,
        "business_fit": None,
        "commercial_viability": None,
        "latency_ms": {},
        "token_usage": None,
        "cost": None,
        "retry_requested": False,
        "errors": [],
        "modal_actual_called": False,
    }
    missing = _missing_requirements(args)
    if missing:
        report["status"] = "blocked"
        report["errors"].append({"error_code": "missing_prerequisite", "missing": missing})
        _write_report(report)
        print(json.dumps({"status": "blocked", "missing": missing, "report": str(OUTPUT_DIR / "quality_gate_result.json")}, ensure_ascii=False))
        return 0

    if not args.actual:
        result = deterministic_gate(request=VLMQualityRequest(stage="background", business_type="cafe"), detected_text=[])
        report.update(
            {
                "status": "dry_run",
                "background_decision": result.decision,
                "fake_text": result.fake_text.model_dump(mode="json"),
                "watermark": result.watermark.model_dump(mode="json"),
                "copy_safe_area": result.copy_safe_area.model_dump(mode="json"),
            }
        )
        _write_report(report)
        print(json.dumps({"status": "dry_run", "report": str(OUTPUT_DIR / "quality_gate_result.json")}, ensure_ascii=False))
        return 0

    if args.max_images != 1:
        report["status"] = "blocked"
        report["errors"].append({"error_code": "max_images_must_be_one", "message": "This smoke runner permits one generated image at most."})
        _write_report(report)
        print(json.dumps({"status": "blocked", "report": str(OUTPUT_DIR / "quality_gate_result.json")}, ensure_ascii=False))
        return 0

    prompt = (
        "Premium realistic commercial cafe drink advertising background, clean blank negative space, "
        "no visible text, no signage, no logo, no watermark, ready for later Korean copy overlay."
    )
    try:
        from orchestrator.app.t2i.engines.registry import get_t2i_engine

        t2i_output = get_t2i_engine(args.engine).generate(
            T2IGenerationInput(
                job_id=report["run_id"],
                prompt=prompt,
                negative_prompt="text, letters, logos, watermark, signage",
                width=1024,
                height=1024,
                num_images=1,
                output_dir=str(OUTPUT_DIR),
                metadata={"case": args.case, "smoke": "vlm_quality_gate_v1"},
            )
        )
    except Exception as exc:
        report["status"] = "blocked"
        report["errors"].append({"error_code": getattr(exc, "error_code", "flux2_klein_actual_failed"), "message": str(exc)[:500]})
        _write_report(report)
        print(json.dumps({"status": "blocked", "report": str(OUTPUT_DIR / "quality_gate_result.json")}, ensure_ascii=False))
        return 0

    image_path = t2i_output.image_paths[0] if t2i_output.image_paths else None
    quality_result = deterministic_gate(request=VLMQualityRequest(stage="background", business_type="cafe"), detected_text=[])
    report.update(
        {
            "status": "success" if image_path else "blocked",
            "generated_image_path": image_path,
            "image_engine": t2i_output.engine,
            "image_metadata": _redact_metadata(t2i_output.metadata),
            "background_decision": quality_result.decision,
            "fake_text": quality_result.fake_text.model_dump(mode="json"),
            "watermark": quality_result.watermark.model_dump(mode="json"),
            "copy_safe_area": quality_result.copy_safe_area.model_dump(mode="json"),
        }
    )
    _write_report(report)
    print(json.dumps({"status": report["status"], "image_path": image_path, "report": str(OUTPUT_DIR / "quality_gate_result.json")}, ensure_ascii=False))
    return 0


def _missing_requirements(args) -> list[str]:
    missing = []
    if args.engine != FLUX2_KLEIN_ENGINE:
        missing.append("engine must be flux2_klein_4b")
    if getattr(args, "actual", False) and os.getenv("EASYADS_VLM_ACTUAL") != "1":
        missing.append("EASYADS_VLM_ACTUAL=1")
        return missing
    if args.backend == "local_diffusers":
        if not get_hf_token():
            missing.append("HF_TOKEN_or_HUGGINGFACE_TOKEN")
            return missing
        try:
            import torch  # noqa: F401
            import diffusers  # noqa: F401
        except Exception:
            missing.append("torch_or_diffusers")
    if args.backend == "modal":
        missing.append("modal_actual_forbidden_in_this_task")
    return missing


def _write_report(report: dict) -> None:
    (OUTPUT_DIR / "quality_gate_result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _redact_metadata(metadata: dict) -> dict:
    blocked = {"token", "api_key", "secret", "authorization", "hf_token", "openai_api_key"}
    output = {}
    for key, value in metadata.items():
        if any(part in key.lower() for part in blocked):
            output[f"{key}_present"] = bool(value)
        elif isinstance(value, str) and len(value) > 300:
            output[key] = value[:297] + "..."
        else:
            output[key] = value
    return output


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=FLUX2_KLEIN_ENGINE)
    parser.add_argument("--backend", default="local_diffusers")
    parser.add_argument("--case", default="cafe_summer_drink")
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--max-images", type=int, default=1)
    parser.add_argument("--max-api-calls", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
