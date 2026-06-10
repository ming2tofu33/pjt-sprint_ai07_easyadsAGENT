"""Guarded Copy Quality Core v2 visual actual E2E runner."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageChops
from pydantic import BaseModel, Field

from orchestrator.app.llm.copy_visual_intent import resolve_copy_visual_intent
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import MarketingCopy, MarketingContext
from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.settings import load_t2i_settings

from scripts._actual_env import load_env_file


VISUAL_CASES = {
    "macaron_collection_001": {
        "prompt": "premium editorial macaron collection, product stack on the right, clean warm negative space on the left, soft daylight, elegant dessert photography, no text, no letters, no numbers, no logo, no watermark, no signature, no menu labels",
        "baseline": {"headline": "대표 메뉴를 지금 확인하세요", "subcopy": "필요한 정보를 간결하게 안내", "cta": "자세히 보기"},
    },
    "restaurant_bbq_001": {
        "prompt": "premium Korean charcoal grilled meat, food hero on the right or lower-right, warm dark restaurant atmosphere, clean negative space on the left, no text, no letters, no numbers, no logo, no watermark, no signature, no menu labels",
        "baseline": {"headline": "회식은 역시 고기", "subcopy": "든든하게 즐기는 우리 가게 대표 메뉴", "cta": "지금 예약하기"},
    },
    "beauty_nail_001": {
        "prompt": "elegant Korean nail salon campaign, hands and nail detail on the right, soft peach neutral background, clean negative space on the left, no text, no letters, no numbers, no logo, no watermark, no signature, no menu labels",
        "baseline": {"headline": "방문 전 네일 서비스로 편하게", "subcopy": "기다림을 줄이고 원하는 시간을 맞춰요", "cta": "지금 예약하기"},
    },
}


VISUAL_CONTEXTS = {
    "macaron_collection_001": {"business_type": "macaron", "item_or_service": "마카롱 컬렉션", "promotion_goal": "menu_discovery", "brand_tone": "premium"},
    "restaurant_bbq_001": {"business_type": "restaurant_bbq", "item_or_service": "숯불구이", "promotion_goal": "reservation_cta", "brand_tone": "premium"},
    "beauty_nail_001": {"business_type": "beauty_nail", "item_or_service": "네일 디자인", "promotion_goal": "reservation_cta", "brand_tone": "premium"},
}


REFERENCE_FIXTURES = {
    "macaron_collection_001": {
        "layout_hint": "editorial left text right product",
        "typography_hint": "premium serif with restrained sans body",
        "style_keywords": ["editorial", "minimal", "premium", "negative space"],
    }
}


class CopyActualComparisonResult(BaseModel):
    baseline_copy_score: float
    v2_copy_score: float
    baseline_natural_korean: float
    v2_natural_korean: float
    baseline_business_fit: float
    v2_business_fit: float
    baseline_specificity: float
    v2_specificity: float
    baseline_emotional_pull: float
    v2_emotional_pull: float
    baseline_cta_relevance: float
    v2_cta_relevance: float
    baseline_generic_phrase: bool
    v2_generic_phrase: bool
    baseline_unsupported_claim: bool
    v2_unsupported_claim: bool
    baseline_text_readable: bool
    v2_text_readable: bool
    copy_matches_product: bool = True
    wrong_domain_terms: list[str] = Field(default_factory=list)
    cta_needed: bool = False
    cta_style_fit: float = 0.0
    information_hierarchy_fit: float = 0.0
    reference_style_alignment: float = 0.0
    preferred_version: Literal["baseline", "v2", "tie"]
    improvement_reasons: list[str] = Field(default_factory=list)
    remaining_copy_issues: list[str] = Field(default_factory=list)
    layout_issues: list[str] = Field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--copy-report")
    parser.add_argument("--cases", nargs="*", default=list(VISUAL_CASES))
    parser.add_argument("--seeds", nargs="*", type=int, default=[42, 43, 44])
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--max-vlm-calls", type=int, default=3)
    parser.add_argument("--output-dir", default="data/outputs/copy_quality_core_v2/visual")
    parser.add_argument("--env-file", default="docs/api_key.env")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"visual_actual_summary_{report['status']}_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] == "completed":
        (output_dir / "visual_actual_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 0 if report["status"] in {"completed", "dry_run"} else 2


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    env_file = load_env_file(getattr(args, "env_file", None))
    missing = missing_actual_requirements(args)
    selected_cases = [case for case in args.cases[: max(1, args.max_images)] if case in VISUAL_CASES]
    copy_report = None
    runs: list[dict[str, Any]] = []
    if not args.actual:
        status = "dry_run"
    elif missing:
        status = "blocked"
    else:
        status = "completed"
        try:
            copy_report = load_copy_report(args.copy_report)
        except Exception as exc:
            status = "failed"
            report_load_error = {"error_code": type(exc).__name__, "error_message": str(exc)}
        else:
            report_load_error = None
    for index, case_id in enumerate(selected_cases):
        if status == "blocked":
            runs.append(blocked_case(case_id, missing))
            continue
        if status == "dry_run":
            runs.append({"case_id": case_id, "status": "dry_run", "missing_requirements": []})
            continue
        if status == "failed" and locals().get("report_load_error"):
            runs.append({"case_id": case_id, "status": "failed", **report_load_error})
            continue
        case_dir = Path(args.output_dir) / case_id
        try:
            run = run_actual_copy_case(case_id, case_dir=case_dir, seed=args.seeds[index] if index < len(args.seeds) else None, copy_report=copy_report, max_vlm_calls=args.max_vlm_calls)
        except Exception as exc:
            run = {"case_id": case_id, "status": "failed", "error_code": type(exc).__name__, "error_message": str(exc)}
        if run.get("status") != "completed":
            status = "failed"
        runs.append(run)
    return {
        "schema_version": "copy_quality_visual_actual_v2",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "actual_requested": args.actual,
        "env_file": env_file,
        "missing_requirements": missing,
        "flux_settings": flux_settings_summary(),
        "runs": runs,
    }


def run_actual_copy_case(case_id: str, *, case_dir: Path, seed: int | None, copy_report: dict[str, Any] | None, max_vlm_calls: int) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    background = generate_flux2_background(case_id, case_dir=case_dir, seed=seed)
    assert_actual_flux_result(background)
    background_path = Path(background.image_paths[0])
    selected_copy = select_v2_copy(case_id, copy_report)
    baseline_copy = VISUAL_CASES[case_id]["baseline"]
    baseline_path = render_copy_variant(case_id, background_path, baseline_copy, case_dir / "baseline", "previous_baseline", selected_reference_template=None)
    previous_v2_path = render_copy_variant(case_id, background_path, selected_copy, case_dir / "previous_v2", "previous_v2", selected_reference_template=None)
    grounded_path = render_copy_variant(case_id, background_path, selected_copy, case_dir / "grounded_intent_v1", "grounded_intent_v1", selected_reference_template=REFERENCE_FIXTURES.get(case_id))
    assert_actual_composite(background_path, baseline_path, baseline_copy)
    assert_actual_composite(background_path, previous_v2_path, selected_copy)
    assert_actual_composite(background_path, grounded_path, selected_copy, selected_reference_template=REFERENCE_FIXTURES.get(case_id))
    sheet_path = build_comparison_sheet_3way(baseline_path, previous_v2_path, grounded_path, case_dir / "comparison_sheet_3way.png")
    vlm = run_vlm_comparison_compat(case_id, baseline_path, previous_v2_path, grounded_path) if max_vlm_calls > 0 else None
    assert_actual_vlm_result(vlm)
    result = {
        "case_id": case_id,
        "status": "completed",
        "flux2_klein_actual_image_generation": True,
        "openai_vlm_actual_final_judge": True,
        "background_path": str(background_path),
        "previous_baseline_path": str(baseline_path),
        "previous_v2_path": str(previous_v2_path),
        "grounded_intent_v1_path": str(grounded_path),
        "baseline_final_path": str(baseline_path),
        "v2_final_path": str(grounded_path),
        "comparison_sheet_path": str(sheet_path),
        "flux_result": background.model_dump(),
        "selected_copy": selected_copy,
        "vlm_result": vlm.model_dump() if hasattr(vlm, "model_dump") else vlm,
    }
    (case_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_vlm_comparison_compat(case_id: str, baseline_path: Path, previous_v2_path: Path, grounded_path: Path) -> CopyActualComparisonResult:
    try:
        return run_actual_vlm_comparison(case_id, baseline_path, previous_v2_path, grounded_path)
    except TypeError:
        return run_actual_vlm_comparison(case_id, baseline_path, previous_v2_path)


def render_copy_variant(
    case_id: str,
    background_path: Path,
    copy: dict[str, str],
    output_dir: Path,
    label: str,
    *,
    selected_reference_template: dict[str, Any] | None,
) -> Path:
    try:
        return render_baseline_and_v2_copy(case_id, background_path, copy, output_dir, label, selected_reference_template=selected_reference_template)
    except TypeError:
        return render_baseline_and_v2_copy(case_id, background_path, copy, output_dir, label)


def generate_flux2_background(case_id: str, *, case_dir: Path, seed: int | None) -> T2IGenerationOutput:
    engine = get_t2i_engine("flux2_klein_4b")
    return engine.generate(
        T2IGenerationInput(
            job_id=f"copy_quality_{case_id}",
            prompt=VISUAL_CASES[case_id]["prompt"],
            negative_prompt="text, letters, numbers, logo, watermark, menu labels",
            width=1024,
            height=1024,
            num_images=1,
            seed=seed,
            output_dir=str(case_dir),
            metadata={"case_id": case_id, "runner": "copy_quality_visual_actual"},
        )
    )


def render_baseline_and_v2_copy(
    case_id: str,
    background_path: Path,
    copy: dict[str, str],
    output_dir: Path,
    label: str,
    *,
    selected_reference_template: dict[str, Any] | None = None,
) -> Path:
    context = MarketingContext(**VISUAL_CONTEXTS[case_id])
    intent = resolve_copy_visual_intent(context, selected_reference_template=selected_reference_template)
    state = {
        "job_id": f"{case_id}_{label}",
        "thread_id": f"{case_id}_thread",
        "t2i_result": {"image_paths": [str(background_path)]},
        "context": context.model_dump(),
        "marketing_copy": MarketingCopy(headline=copy["headline"], subcopy=copy.get("subcopy"), cta=copy.get("cta")).model_dump(),
        "copy_visual_intent": intent.model_dump(),
        "selected_reference_template": selected_reference_template,
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024},
        "current_brief": {},
    }
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))
    result = text_renderer_node(state)
    assert result.get("status") == "overlaying_text", result
    rendered = Path(result["final_image_path"])
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{label}_final.png"
    target.write_bytes(rendered.read_bytes())
    return target


def run_actual_vlm_comparison(case_id: str, baseline_path: Path, previous_v2_path: Path, grounded_path: Path | None = None) -> CopyActualComparisonResult:
    grounded_path = grounded_path or previous_v2_path
    model = os.getenv("LLM_OPENAI_VISION_MODEL") or os.getenv("EASYADS_LLM_VISION_MODEL") or "gpt-4.1-mini"
    prompt = (
        "Compare two Korean ad creatives. Return strict JSON only with these keys: "
        "baseline_copy_score, v2_copy_score, baseline_natural_korean, v2_natural_korean, "
        "baseline_business_fit, v2_business_fit, baseline_specificity, v2_specificity, "
        "baseline_emotional_pull, v2_emotional_pull, baseline_cta_relevance, v2_cta_relevance, "
        "baseline_generic_phrase, v2_generic_phrase, baseline_unsupported_claim, v2_unsupported_claim, "
        "baseline_text_readable, v2_text_readable, preferred_version, improvement_reasons, "
        "remaining_copy_issues, layout_issues, copy_matches_product, wrong_domain_terms, cta_needed, "
        "cta_style_fit, information_hierarchy_fit, reference_style_alignment. "
        "preferred_version must be baseline, v2, or tie. Never prefer v2 when copy_matches_product is false, "
        "wrong_domain_terms is non-empty, v2_business_fit is below 6, or v2_unsupported_claim is true. "
        f"Case id: {case_id}. First image is baseline. Second image is previous Copy Quality v2. Third image is grounded_intent_v1. Prefer v2 only when grounded_intent_v1 is best; encode preferred_version as baseline, v2, or tie for backward compatibility."
    )
    response = _create_openai_vision_response(model=model, prompt=prompt, image_paths=[baseline_path, previous_v2_path, grounded_path])
    text = _extract_response_text(response)
    payload = normalize_vlm_payload(json.loads(_strip_json_fence(text)))
    return CopyActualComparisonResult.model_validate(payload)


def normalize_vlm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    score_fields = {
        "baseline_copy_score",
        "v2_copy_score",
        "baseline_natural_korean",
        "v2_natural_korean",
        "baseline_business_fit",
        "v2_business_fit",
        "baseline_specificity",
        "v2_specificity",
        "baseline_emotional_pull",
        "v2_emotional_pull",
        "baseline_cta_relevance",
        "v2_cta_relevance",
    }
    bool_fields = {
        "baseline_generic_phrase",
        "v2_generic_phrase",
        "baseline_unsupported_claim",
        "v2_unsupported_claim",
        "baseline_text_readable",
        "v2_text_readable",
        "copy_matches_product",
    }
    list_fields = {"improvement_reasons", "remaining_copy_issues", "layout_issues", "wrong_domain_terms"}
    for field in score_fields:
        normalized[field] = float(normalized.get(field, 0) or 0)
    for field in ("cta_style_fit", "information_hierarchy_fit", "reference_style_alignment"):
        normalized[field] = float(normalized.get(field, 0) or 0)
    for field in bool_fields:
        value = normalized.get(field, True if field == "copy_matches_product" else False)
        if isinstance(value, bool):
            normalized[field] = value
        elif isinstance(value, (int, float)):
            normalized[field] = value >= 5
        elif isinstance(value, str):
            normalized[field] = value.strip().lower() in {"true", "yes", "1", "high", "present", "readable"}
        else:
            normalized[field] = True if field == "copy_matches_product" else False
    for field in list_fields:
        value = normalized.get(field, [])
        if isinstance(value, list):
            normalized[field] = [str(item) for item in value]
        elif value:
            normalized[field] = [str(value)]
        else:
            normalized[field] = []
    preferred = str(normalized.get("preferred_version", "tie")).strip().lower()
    if not normalized.get("copy_matches_product", True) or normalized.get("wrong_domain_terms") or normalized.get("v2_business_fit", 0) < 6 or normalized.get("v2_unsupported_claim"):
        preferred = "baseline" if normalized.get("baseline_business_fit", 0) >= normalized.get("v2_business_fit", 0) else "tie"
    normalized["preferred_version"] = preferred if preferred in {"baseline", "v2", "tie"} else "tie"
    return normalized


def _create_openai_vision_response(*, model: str, prompt: str, image_paths: list[Path]) -> Any:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("openai_sdk_unavailable_for_vlm_actual") from exc

    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for image_path in image_paths:
        content.append({"type": "input_image", "image_url": _image_data_url(image_path)})
    return OpenAI().responses.create(model=model, input=[{"role": "user", "content": content}], temperature=0)


def _image_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    if isinstance(response, dict) and response.get("output_text"):
        return str(response["output_text"])
    raise RuntimeError("openai_vlm_response_missing_output_text")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    return stripped


def validate_actual_artifacts(run: dict[str, Any]) -> bool:
    try:
        assert_actual_flux_result(T2IGenerationOutput(**run["flux_result"]))
        assert Path(run["baseline_final_path"]).exists()
        assert Path(run["v2_final_path"]).exists()
        assert Path(run["comparison_sheet_path"]).exists()
    except Exception:
        return False
    return True


def assert_actual_openai_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("fallback_used") or metadata.get("provider") in {None, "mock"}:
        raise AssertionError("OpenAI actual metadata is missing or fallback/mock was used.")
    if not metadata.get("model_name") and not metadata.get("model"):
        raise AssertionError("OpenAI actual model id is missing.")
    usage = metadata.get("token_usage") or {}
    if not usage or usage.get("input_tokens", 0) <= 0 or usage.get("output_tokens", 0) <= 0:
        raise AssertionError("OpenAI actual token usage is missing.")


def assert_actual_flux_result(result: T2IGenerationOutput) -> None:
    if result.engine != "flux2_klein_4b":
        raise AssertionError("FLUX actual result must use flux2_klein_4b.")
    metadata = result.metadata or {}
    if metadata.get("provider") == "mock" or metadata.get("execution_backend") != "local_diffusers":
        raise AssertionError("FLUX actual result must use local_diffusers and not mock.")
    if metadata.get("model_name") != "black-forest-labs/FLUX.2-klein-4B":
        raise AssertionError("FLUX actual model name is missing.")
    if not result.image_paths or not Path(result.image_paths[0]).exists():
        raise AssertionError("FLUX actual image path is missing.")
    with Image.open(result.image_paths[0]) as image:
        image.verify()
    if not result.latency_ms or result.latency_ms <= 0:
        raise AssertionError("FLUX actual latency is missing.")


def assert_actual_composite(background_path: Path, composite_path: Path, expected_copy: dict[str, str], *, selected_reference_template: dict[str, Any] | None = None) -> None:
    if not composite_path.exists() or composite_path.stat().st_size <= 0:
        raise AssertionError("Composite image is missing.")
    with Image.open(composite_path) as image:
        image.verify()
    with Image.open(background_path).convert("RGB") as bg, Image.open(composite_path).convert("RGB") as final:
        if not ImageChops.difference(bg, final).getbbox():
            raise AssertionError("Composite image is identical to background.")
    context = MarketingContext(**VISUAL_CONTEXTS.get(composite_path.parent.parent.name, {})) if composite_path.parent.parent.name in VISUAL_CONTEXTS else None
    intent = resolve_copy_visual_intent(context, selected_reference_template=selected_reference_template) if context else None
    for key in ("headline", "subcopy"):
        if not expected_copy.get(key):
            raise AssertionError(f"Expected {key} is missing.")
    if intent and intent.cta_visibility != "hidden" and intent.cta_style != "none" and not expected_copy.get("cta"):
        raise AssertionError("Expected cta is missing.")


def assert_actual_vlm_result(result: Any) -> None:
    if result is None:
        raise AssertionError("VLM actual result is missing.")
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    if data.get("preferred_version") not in {"baseline", "v2", "tie"}:
        raise AssertionError("VLM structured result is invalid.")


def build_comparison_sheet(left: Path, right: Path, output_path: Path) -> Path:
    with Image.open(left).convert("RGB") as left_image, Image.open(right).convert("RGB") as right_image:
        sheet = Image.new("RGB", (left_image.width + right_image.width, left_image.height + 64), "white")
        sheet.paste(left_image, (0, 64))
        sheet.paste(right_image, (left_image.width, 64))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
    return output_path


def build_comparison_sheet_3way(left: Path, middle: Path, right: Path, output_path: Path) -> Path:
    with Image.open(left).convert("RGB") as left_image, Image.open(middle).convert("RGB") as middle_image, Image.open(right).convert("RGB") as right_image:
        sheet = Image.new("RGB", (left_image.width + middle_image.width + right_image.width, left_image.height + 64), "white")
        sheet.paste(left_image, (0, 64))
        sheet.paste(middle_image, (left_image.width, 64))
        sheet.paste(right_image, (left_image.width + middle_image.width, 64))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
    return output_path


def select_v2_copy(case_id: str, report: dict[str, Any] | None, *, allow_placeholder: bool = False) -> dict[str, str]:
    for run in (report or {}).get("runs", []):
        if run.get("case_id") == case_id and run.get("selected_copy"):
            return run["selected_copy"]
    if not allow_placeholder:
        raise ValueError(f"selected_copy_missing:{case_id}")
    return {"headline": "Copy Quality v2", "subcopy": "선택된 카피가 필요합니다", "cta": "문의하기"}


def load_copy_report(path: str | None) -> dict[str, Any] | None:
    if not path:
        raise ValueError("copy_report_required_for_actual")
    report_path = Path(path)
    if not report_path.exists():
        raise FileNotFoundError(path)
    return json.loads(report_path.read_text(encoding="utf-8"))


def missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    if not args.actual:
        return []
    missing: list[str] = []
    if os.getenv("EASYADS_COPY_QUALITY_ACTUAL") != "1":
        missing.append("EASYADS_COPY_QUALITY_ACTUAL=1")
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if os.getenv("EASYADS_VLM_ACTUAL") != "1":
        missing.append("EASYADS_VLM_ACTUAL=1")
    if os.getenv("EASYADS_FLUX2_KLEIN_ACTUAL") != "1":
        missing.append("EASYADS_FLUX2_KLEIN_ACTUAL=1")
    settings = load_t2i_settings()
    if not settings.enable_flux2_klein_local:
        missing.append("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL=true")
    if settings.flux2_klein_backend != "local_diffusers":
        missing.append("EASYADS_T2I_FLUX2_KLEIN_BACKEND=local_diffusers")
    if not str(settings.flux2_klein_device).startswith("cuda"):
        missing.append("EASYADS_T2I_FLUX2_KLEIN_DEVICE=cuda")
    return missing


def blocked_case(case_id: str, missing: list[str]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "blocked",
        "flux2_klein_actual_image_generation": False,
        "openai_vlm_actual_final_judge": False,
        "quality": None,
        "copy_safe_area": None,
        "business_fit": None,
        "missing_requirements": missing,
    }


def flux_settings_summary() -> dict[str, Any]:
    settings = load_t2i_settings()
    return {
        "engine": "flux2_klein_4b",
        "model_name": settings.flux2_klein_model_id,
        "backend": settings.flux2_klein_backend,
        "device": settings.flux2_klein_device,
        "dtype": settings.flux2_klein_dtype,
        "cpu_offload": settings.flux2_klein_enable_cpu_offload,
        "steps": settings.flux2_klein_num_inference_steps,
        "guidance_scale": settings.flux2_klein_guidance_scale,
    }


if __name__ == "__main__":
    raise SystemExit(main())
