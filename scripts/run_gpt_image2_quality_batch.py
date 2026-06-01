"""GPT-image-2 actual quality batch runner.

Runs through GenerationJob API. Dry-run and blocked reports never call external APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.app.api.app import create_app  # noqa: E402
from orchestrator.app.llm.visual_templates import select_visual_template  # noqa: E402
from orchestrator.app.reference_catalog.service import load_reference_templates, search_reference_templates  # noqa: E402
from orchestrator.app.schemas.reference_catalog import ReferenceTemplate, ReferenceTemplateSearchQuery  # noqa: E402

BATCH_ID = "gpt_image2_quality_batch_v1"
SCHEMA_VERSION = "gpt_image2_quality_batch_report_v1"
RUN_MODE = "gpt_image_2_actual"
MAX_CASES_HARD_CAP = 6
IMAGES_PER_CASE = 1


@dataclass(frozen=True)
class QualityBatchCase:
    case_id: str
    business_type: str
    category: str
    ad_format: str
    platform: str
    aspect_ratio: str
    user_input: str
    quality_focus: list[str]


def get_quality_batch_cases() -> list[QualityBatchCase]:
    return [
        QualityBatchCase(
            case_id="cafe_dessert_001",
            business_type="cafe",
            category="cafe",
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="1:1",
            user_input=(
                "Create an Instagram feed advertising background for a new strawberry latte menu. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Make it a premium cafe dessert scene with a clean empty area for Korean text overlay."
            ),
            quality_focus=["premium cafe mood", "text safe area", "no fake text", "strawberry latte appeal"],
        ),
        QualityBatchCase(
            case_id="restaurant_bbq_001",
            business_type="restaurant",
            category="restaurant",
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="1:1",
            user_input=(
                "Create an Instagram feed advertising background for a premium Korean BBQ restaurant. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Use warm lighting, appetizing grilled food atmosphere, and a clean reserved area for text overlay."
            ),
            quality_focus=["appetizing food", "warm lighting", "text safe area", "no signage text"],
        ),
        QualityBatchCase(
            case_id="beauty_salon_001",
            business_type="beauty",
            category="beauty",
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="1:1",
            user_input=(
                "Create an Instagram feed advertising background for a beauty salon campaign. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Use a clean, trustworthy, premium beauty mood with a clear empty area for Korean text overlay."
            ),
            quality_focus=["premium beauty mood", "clean studio", "text safe area", "trustworthy visual"],
        ),
        QualityBatchCase(
            case_id="cafe_story_001",
            business_type="cafe",
            category="cafe",
            ad_format="instagram_story",
            platform="instagram",
            aspect_ratio="9:16",
            user_input=(
                "Create a vertical Instagram story advertising background for a cafe drink promotion. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Feature a premium drink hero composition with clean vertical space for Korean text overlay."
            ),
            quality_focus=["story layout", "drink hero", "vertical text space", "no fake text"],
        ),
        QualityBatchCase(
            case_id="restaurant_event_001",
            business_type="restaurant",
            category="restaurant",
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="1:1",
            user_input=(
                "Create an Instagram feed advertising background for a restaurant event promotion. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Show a warm, abundant, appetizing food scene with clean space for later text overlay."
            ),
            quality_focus=["promotion background", "food abundance", "clean text area", "no logo"],
        ),
        QualityBatchCase(
            case_id="beauty_clean_001",
            business_type="beauty",
            category="beauty",
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="1:1",
            user_input=(
                "Create a minimalist premium beauty consultation advertising background. "
                "Do not include any text, letters, signage, logos, or watermarks inside the image. "
                "Use a bright clean salon mood, soft lighting, and a clear reserved area for Korean text overlay."
            ),
            quality_focus=["minimal premium", "reservation ad", "bright clean mood", "text safe area"],
        ),
    ]


def build_env_summary() -> dict[str, bool]:
    return {
        "external_t2i_enabled": _env_bool("EASYADS_ENABLE_EXTERNAL_T2I"),
        "gpt_image_2_enabled": _env_bool("EASYADS_ENABLE_GPT_IMAGE_2"),
        "openai_api_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "quality_batch_confirmed": _env_bool("EASYADS_QUALITY_BATCH_CONFIRM"),
    }


def missing_actual_requirements(env: dict[str, bool], confirm_cost: bool) -> list[str]:
    checks = [
        ("EASYADS_ENABLE_EXTERNAL_T2I", env["external_t2i_enabled"]),
        ("EASYADS_ENABLE_GPT_IMAGE_2", env["gpt_image_2_enabled"]),
        ("OPENAI_API_KEY", env["openai_api_key_present"]),
        ("EASYADS_QUALITY_BATCH_CONFIRM", env["quality_batch_confirmed"]),
        ("--confirm-cost", confirm_cost),
    ]
    return [name for name, ok in checks if not ok]


def select_reference_template_for_case(case: QualityBatchCase) -> ReferenceTemplate | None:
    queries = [
        ReferenceTemplateSearchQuery(
            category=case.category,
            business_type=case.business_type,
            ad_format=case.ad_format,
            platform=case.platform,
            aspect_ratio=case.aspect_ratio,
            limit=10,
            sort_by="relevance",
        ),
        ReferenceTemplateSearchQuery(
            category=case.category,
            business_type=case.business_type,
            limit=10,
            sort_by="relevance",
        ),
        ReferenceTemplateSearchQuery(
            business_type=case.business_type,
            limit=10,
            sort_by="relevance",
        ),
    ]
    for query in queries:
        result = search_reference_templates(query)
        if result.items:
            return result.items[0]
    candidates = load_reference_templates()
    return max(candidates, key=lambda template: template.popularity_score, default=None)


def build_generation_payload(case: QualityBatchCase, template: ReferenceTemplate | None) -> dict[str, Any]:
    return {
        "user_input": case.user_input,
        "run_mode": RUN_MODE,
        "selected_reference_template_id": template.template_id if template else None,
        "ad_format": case.ad_format,
        "metadata": {
            "quality_batch_id": BATCH_ID,
            "case_id": case.case_id,
            "quality_focus": case.quality_focus,
            "business_type": case.business_type,
            "category": case.category,
            "platform": case.platform,
            "aspect_ratio": case.aspect_ratio,
            "images_per_case": IMAGES_PER_CASE,
        },
    }


def run_quality_batch(actual: bool, dry_run: bool, max_cases: int, confirm_cost: bool, output_dir: Path) -> dict[str, Any]:
    if max_cases < 1 or max_cases > MAX_CASES_HARD_CAP:
        raise ValueError("--max-cases must be between 1 and 6")
    if actual and dry_run:
        raise ValueError("Choose either --actual or --dry-run, not both")

    started = perf_counter()
    env = build_env_summary()
    cases = get_quality_batch_cases()[:max_cases]
    missing = missing_actual_requirements(env, confirm_cost)
    status = "dry_run" if dry_run or not actual else "blocked" if missing else "running"
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": BATCH_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actual_generation": bool(actual and not dry_run and not missing),
        "status": status,
        "max_cases": max_cases,
        "images_per_case": IMAGES_PER_CASE,
        "total_max_images": max_cases * IMAGES_PER_CASE,
        "total_cases": len(cases),
        "total_success": 0,
        "total_failed": 0,
        "env": env,
        "missing_requirements": missing,
        "cases": [],
        "notes": [],
    }

    if dry_run or not actual:
        report["notes"].append("Dry-run only. No GPT-image-2 API call was made.")
        for case in cases:
            report["cases"].append(_planned_case_record(case))
        return _finish_report(report, started, output_dir)

    if missing:
        report["status"] = "blocked"
        report["reason"] = "missing_actual_generation_requirements"
        report["notes"].append("Refusing actual generation. Pass --confirm-cost and set required env flags.")
        for case in cases:
            report["cases"].append(_planned_case_record(case))
        return _finish_report(report, started, output_dir)

    print("Actual GPT-image-2 generation will run.")
    print(f"Max cases: {max_cases}")
    print("Images per case: 1")
    print(f"Total max images: {max_cases}")
    print("External API: OpenAI image generation")
    print("Output directory: data/outputs")
    print(f"Report directory: {output_dir.as_posix()}")

    client = TestClient(create_app())
    for case in cases:
        case_started = perf_counter()
        template = select_reference_template_for_case(case)
        payload = build_generation_payload(case, template)
        visual_template = select_visual_template(
            case.business_type,
            case.ad_format,
            "premium",
            _template_hint(template),
        )
        response = client.post("/api/v1/generation-jobs", json=payload)
        response_payload = response.json()
        job = response_payload.get("job") or {}
        result_payload = job.get("result_payload") or {}
        error = job.get("error")
        success = response.status_code < 400 and job.get("status") == "done"
        report["total_success" if success else "total_failed"] += 1
        report["cases"].append(
            _case_result_record(
                case=case,
                template=template,
                visual_template_id=visual_template.template_id,
                job=job,
                result_payload=result_payload,
                status_code=response.status_code,
                latency_ms=int((perf_counter() - case_started) * 1000),
                error=error,
            )
        )
    report["status"] = "success" if report["total_failed"] == 0 else "failed"
    return _finish_report(report, started, output_dir)


def _planned_case_record(case: QualityBatchCase) -> dict[str, Any]:
    template = select_reference_template_for_case(case)
    visual_template = select_visual_template(case.business_type, case.ad_format, "premium", _template_hint(template))
    payload = build_generation_payload(case, template)
    return {
        "case_id": case.case_id,
        "status": "planned",
        "business_type": case.business_type,
        "category": case.category,
        "ad_format": case.ad_format,
        "platform": case.platform,
        "aspect_ratio": case.aspect_ratio,
        "selected_reference_template_id": payload["selected_reference_template_id"],
        "selected_reference_template_title": template.title if template else None,
        "visual_template_id": visual_template.template_id,
        "payload": _safe_payload_preview(payload),
        "quality_focus": case.quality_focus,
        "would_call_actual_engine": False,
    }


def _case_result_record(
    *,
    case: QualityBatchCase,
    template: ReferenceTemplate | None,
    visual_template_id: str,
    job: dict[str, Any],
    result_payload: dict[str, Any],
    status_code: int,
    latency_ms: int,
    error: Any,
) -> dict[str, Any]:
    metadata = job.get("metadata") or {}
    return {
        "case_id": case.case_id,
        "status_code": status_code,
        "job_id": job.get("job_id"),
        "thread_id": job.get("thread_id"),
        "status": job.get("status"),
        "run_mode": metadata.get("requested_run_mode"),
        "selected_reference_template_id": job.get("selected_reference_template_id") or (template.template_id if template else None),
        "selected_reference_template_title": template.title if template else None,
        "visual_template_id": visual_template_id,
        "engine": metadata.get("engine") or result_payload.get("engine"),
        "latency_ms": latency_ms,
        "output_path": job.get("output_path"),
        "result_payload": _safe_result_payload(result_payload),
        "final_image_path": result_payload.get("final_image_path"),
        "download_path": result_payload.get("download_path"),
        "final_image_url": result_payload.get("final_image_url"),
        "download_url": result_payload.get("download_url"),
        "prompt_summary": result_payload.get("prompt_summary") or {},
        "validation_summary": result_payload.get("validation_summary") or {},
        "copy_summary": result_payload.get("copy_summary") or {},
        "layout_summary": result_payload.get("layout_summary") or {},
        "error": error,
        "quality_focus": case.quality_focus,
        "manual_review": _manual_review_template(),
    }


def _manual_review_template() -> dict[str, Any]:
    return {
        "advertising_fit": None,
        "visual_quality": None,
        "not_tacky": None,
        "text_safe_area": None,
        "reference_alignment": None,
        "business_fit": None,
        "fake_text_or_logo_risk": None,
        "usable_for_mvp": None,
        "notes": "",
    }


def _safe_payload_preview(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_mode": payload.get("run_mode"),
        "selected_reference_template_id": payload.get("selected_reference_template_id"),
        "ad_format": payload.get("ad_format"),
        "metadata": payload.get("metadata"),
        "user_input_hash": hashlib.sha256(str(payload.get("user_input", "")).encode("utf-8")).hexdigest(),
        "user_input_preview": " ".join(str(payload.get("user_input", "")).split())[:160],
    }


def _safe_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "schema_version",
        "job_id",
        "output_dir",
        "background_image_path",
        "final_image_path",
        "metadata_path",
        "prompt_path",
        "validation_path",
        "copy_path",
        "layout_path",
        "render_result_path",
        "download_path",
        "download_url",
        "final_image_url",
        "prompt_summary",
        "validation_summary",
        "copy_summary",
        "layout_summary",
        "has_text_overlay",
        "engine",
        "render_mode",
    }
    return {key: value for key, value in payload.items() if key in allowed_keys}


def _template_hint(template: ReferenceTemplate | None) -> dict[str, Any] | None:
    if not template:
        return None
    return {
        "template_id": template.template_id,
        "style_keywords": template.style_keywords,
        "layout_hint": template.layout_hint,
        "category": template.category,
    }


def _finish_report(report: dict[str, Any], started: float, output_dir: Path) -> dict[str, Any]:
    report["latency_ms"] = int((perf_counter() - started) * 1000)
    json_path, md_path = write_reports(report, output_dir)
    report["report_paths"] = {"json": json_path.as_posix(), "md": md_path.as_posix()}
    return _redact(report)


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"gpt_image2_quality_batch_v1_{timestamp}"
    safe_report = _redact(report)
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(safe_report), encoding="utf-8")
    return json_path, md_path


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GPT-image-2 Quality Batch v1",
        "",
        "## Batch Summary",
        f"- Status: `{report.get('status')}`",
        f"- Actual generation: `{report.get('actual_generation')}`",
        f"- Total cases: `{report.get('total_cases')}`",
        f"- Success: `{report.get('total_success')}`",
        f"- Failed: `{report.get('total_failed')}`",
        f"- Total max images: `{report.get('total_max_images')}`",
        "",
        "## Env Readiness",
        f"- External T2I enabled: `{report['env']['external_t2i_enabled']}`",
        f"- GPT-image-2 enabled: `{report['env']['gpt_image_2_enabled']}`",
        f"- OpenAI API key present: `{report['env']['openai_api_key_present']}`",
        f"- Quality batch confirmed: `{report['env']['quality_batch_confirmed']}`",
        f"- Missing requirements: `{', '.join(report.get('missing_requirements') or []) or 'none'}`",
        "",
        "## Cases",
    ]
    for item in report.get("cases", []):
        lines.extend(
            [
                "",
                f"### {item.get('case_id')}",
                f"- Status: `{item.get('status')}`",
                f"- Job ID: `{item.get('job_id')}`",
                f"- Reference template: `{item.get('selected_reference_template_id')}` / {item.get('selected_reference_template_title')}",
                f"- Visual template: `{item.get('visual_template_id')}`",
                f"- Engine: `{item.get('engine')}`",
                f"- Latency ms: `{item.get('latency_ms')}`",
                f"- Final image path: `{item.get('final_image_path')}`",
                f"- Download URL: `{item.get('download_url')}`",
                "",
                "#### Prompt Summary",
                "```json",
                json.dumps(item.get("prompt_summary") or {}, ensure_ascii=False, indent=2),
                "```",
                "",
                "#### Manual Review",
                "| Metric | Score | Notes |",
                "|---|---:|---|",
                "| Advertising fit | TBD |  |",
                "| Visual quality | TBD |  |",
                "| Not tacky | TBD |  |",
                "| Text safe area | TBD |  |",
                "| Reference alignment | TBD |  |",
                "| Business fit | TBD |  |",
                "| Fake text/logo risk | TBD |  |",
                "| MVP usable | TBD |  |",
                "",
                "#### Failure Types / ImagePrompt v3 Candidates",
                "- TBD after manual image review.",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety Notes",
            "No raw API key, base64 image data, or image bytes are stored in this report.",
            "Generated images under `data/outputs/` and reports under `data/logs/` are runtime artifacts and must not be committed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _redact(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    for secret_name in ("OPENAI_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN"):
        secret = os.getenv(secret_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return json.loads(text)


def _env_bool(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run guarded GPT-image-2 quality batch via GenerationJob API.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--actual", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument("--output-dir", default="data/logs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    actual = bool(args.actual)
    dry_run = bool(args.dry_run or not args.actual)
    try:
        report = run_quality_batch(
            actual=actual,
            dry_run=dry_run,
            max_cases=args.max_cases,
            confirm_cost=bool(args.confirm_cost),
            output_dir=Path(args.output_dir),
        )
    except ValueError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": report["status"], "report_paths": report["report_paths"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
