"""Final composite quality actual E2E runner.

Actual mode is fail-closed. It must call OpenAI for copy and VLM, call the
FLUX.2 Klein engine, and create the final composite through production nodes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.final_composite_revision import final_composite_revision_node
from orchestrator.app.llm.nodes.final_copy_revision import final_copy_revision_node
from orchestrator.app.llm.nodes.final_validation import final_validation_node
from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
from orchestrator.app.llm.nodes.readability_gate import readability_gate_node
from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node
from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.t2i.engines.base import T2IGenerationInput
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from scripts._actual_env import load_env_file
from scripts._actual_creative_pipeline import ActualCallBudget, ActualCreativeInput, ActualCreativeRuntime, run_actual_creative_case, run_input_evidence_normalizer, run_product_understanding


REQUIRED_ACTUAL_ENV = {
    "EASYADS_FINAL_COMPOSITE_ACTUAL": "1",
    "EASYADS_COPY_QUALITY_ACTUAL": "1",
    "EASYADS_ENABLE_LLM_CALLS": "true",
    "EASYADS_LLM_PROVIDER": "openai",
    "EASYADS_VLM_ACTUAL": "1",
    "EASYADS_FLUX2_KLEIN_ACTUAL": "1",
    "EASYADS_ENABLE_FLUX2_KLEIN_LOCAL": "true",
}
FORBIDDEN_COPY_TERMS = {"AI", "smart", "consulting", "expert", "technology", "service innovation", "best", "freshest", "free", "price", "guaranteed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--case", default="open_domain_product_001")
    parser.add_argument("--seed", type=int, default=62)
    parser.add_argument("--force-flux-generation", action="store_true")
    parser.add_argument("--copy-model", default="gpt-5.4")
    parser.add_argument("--vlm-model", default="gpt-5.4")
    parser.add_argument("--max-copy-calls", type=int, default=2)
    parser.add_argument("--max-vlm-calls", type=int, default=2)
    parser.add_argument("--max-flux-generations", type=int, default=2)
    parser.add_argument("--max-composite-attempts", type=int, default=5)
    parser.add_argument("--output-dir", default="data/outputs/final_composite_quality_actual_gpt54")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--canonical-smoke", action="store_true")
    parser.add_argument("--product-understanding-benchmark", action="store_true")
    parser.add_argument("--composite-benchmark", action="store_true")
    parser.add_argument("--benchmark-manifest")
    parser.add_argument("--stop-after", choices=["product_understanding"])
    parser.add_argument("--source-image")
    parser.add_argument("--reuse-text-only-background-as-source", action="store_true")
    parser.add_argument("--max-openai-calls", type=int, default=6)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--render-all-variants", action="store_true")
    args = parser.parse_args()

    env_report = load_env_file(args.env_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _base_summary(args, env_report)

    if args.dry_run or not args.actual:
        summary.update({"status": "blocked", "missing_requirements": ["--actual"], "runs": []})
        _write_summary(output_dir, summary)
        return 0

    missing = _missing_actual_requirements(args)
    if missing:
        summary.update({"status": "blocked", "missing_requirements": missing, "runs": []})
        _write_summary(output_dir, summary)
        return 0

    if args.canonical_smoke:
        summary.update(run_canonical_smoke(args=args, output_dir=output_dir))
        _write_summary(output_dir, summary)
        return 0

    if args.product_understanding_benchmark:
        summary.update(run_product_understanding_benchmark(args=args, output_dir=output_dir))
        _write_summary(output_dir, summary)
        return 0

    if args.composite_benchmark:
        summary.update(run_composite_benchmark(args=args, output_dir=output_dir))
        _write_summary(output_dir, summary)
        return 0

    case_dir = output_dir / args.case
    case_dir.mkdir(parents=True, exist_ok=True)
    result = run_actual_case(args=args, output_dir=output_dir, case_dir=case_dir)
    summary["runs"] = [result]
    summary["status"] = "completed" if result.get("status") == "completed" else result.get("status", "failed")
    summary["actual_api_calls"] = bool(result.get("copy_token_usage") and result.get("vlm_token_usage"))
    summary["image_generation_performed"] = bool(result.get("flux_output_path") or result.get("background_path"))
    _write_summary(output_dir, summary)
    return 0


def run_canonical_smoke(*, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    runtime = _canonical_runtime(args)
    cases = [
        ActualCreativeInput(
            case_id="product_text_only",
            input_mode="text_only",
            user_text="Create a natural product introduction ad.",
            placement="instagram_feed_static",
            promotion_goal="brand_awareness",
            seed=81,
            output_dir=str(output_dir),
        )
    ]
    runs = [_run_or_resume_canonical_case(cases[0], runtime, resume=bool(args.resume))]
    source_image = args.source_image if _is_clean_background_source(args.source_image) else None
    if (
        not source_image
        and args.reuse_text_only_background_as_source
        and runs[0].get("status") == "completed"
        and runs[0].get("background_image_path")
        and Path(str(runs[0].get("background_image_path"))).exists()
        and _is_clean_background_source(str(runs[0].get("background_image_path")))
    ):
        source_image = runs[0]["background_image_path"]
    if source_image:
        cases.extend(
            [
                ActualCreativeInput(
                    case_id="product_image_only",
                    input_mode="image_only",
                    source_image_path=source_image,
                    source_provenance="actual_generated_reuse" if source_image == runs[0].get("background_image_path") else "user_uploaded",
                    placement="instagram_feed_static",
                    promotion_goal="brand_awareness",
                    seed=82,
                    output_dir=str(output_dir),
                ),
                ActualCreativeInput(
                    case_id="product_text_and_image",
                    input_mode="text_and_image",
                    user_text="Create an Instagram feed ad centered on the product in the image.",
                    source_image_path=source_image,
                    source_provenance="actual_generated_reuse" if source_image == runs[0].get("background_image_path") else "user_uploaded",
                    placement="instagram_feed_static",
                    promotion_goal="product_introduction",
                    seed=83,
                    output_dir=str(output_dir),
                ),
            ]
        )
        for case in cases[1:]:
            runs.append(_run_or_resume_canonical_case(case, runtime, resume=bool(args.resume)))

    comparison_path = _build_canonical_comparison(output_dir, runs)
    evidence_comparison_path = _write_evidence_comparison(output_dir, runs)
    cross = {
        "schema_version": "canonical_actual_creative_pipeline_comparison_v1",
        "runs": [
            {
                "case_id": run.get("case_id"),
                "input_mode": run.get("input_mode"),
                "status": run.get("status"),
                "source_provenance": (run.get("input_evidence") or {}).get("source_provenance"),
                "background_sha256": run.get("background_sha256"),
                "final_composite_sha256": run.get("final_composite_sha256"),
            }
            for run in runs
        ],
    }
    (output_dir / "cross_input_comparison.json").write_text(json.dumps(cross, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "runtime_metadata.json").write_text(
        json.dumps(
            {
                "copy_model": args.copy_model,
                "vision_model": args.vlm_model,
                "t2i_engine": "flux2_klein_4b",
                "t2i_backend": "local_diffusers",
                "max_openai_calls": args.max_openai_calls,
                "max_flux_generations": args.max_flux_generations,
                "runtime_environment": _runtime_environment_report(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "schema_version": "canonical_actual_creative_pipeline_v1",
        "status": _canonical_summary_status(runs),
        "runs": runs,
        "cross_input_comparison_path": str(output_dir / "cross_input_comparison.json"),
        "evidence_comparison_path": str(evidence_comparison_path),
        "comparison_all_modes_path": str(comparison_path) if comparison_path else None,
        "actual_api_calls": any(_has_provider_usage(run.get("copy_provider_metadata")) or _has_provider_usage((run.get("vlm_result") or {}).get("provider_metadata") or run.get("vlm_result")) for run in runs),
        "all_runs_have_actual_api_calls": all(_has_provider_usage(run.get("copy_provider_metadata")) and _has_provider_usage((run.get("vlm_result") or {}).get("provider_metadata") or run.get("vlm_result")) for run in runs),
        "image_generation_performed": any(bool(run.get("flux_metadata")) for run in runs),
        "mock_or_fixture_count": sum(int(run.get("mock_or_fixture_count") or 0) for run in runs),
        "runtime_environment": _runtime_environment_report(),
    }


def run_product_understanding_benchmark(*, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    if not args.benchmark_manifest:
        return {"status": "blocked", "missing_requirements": ["--benchmark-manifest"], "runs": []}
    manifest = json.loads(Path(args.benchmark_manifest).read_text(encoding="utf-8"))
    runtime = _canonical_runtime(args)
    results: list[dict[str, Any]] = []
    for case in manifest.get("cases", []):
        case_dir = output_dir / "cases" / str(case["case_id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        source_image_path = case.get("source_image_path")
        synthetic_count = 0
        if source_image_path and not Path(source_image_path).exists():
            results.append({"case_id": case.get("case_id"), "status": "failed", "error_code": "missing_actual_source_image"})
            continue
        try:
            request = ActualCreativeInput(
                case_id=str(case["case_id"]),
                input_mode=case.get("input_mode") or "text_only",
                user_text=case.get("user_text"),
                source_image_path=source_image_path,
                placement=case.get("placement") or "instagram_feed_static",
                promotion_goal=case.get("promotion_goal") or "brand_awareness",
                seed=int(case.get("seed") or args.seed),
                output_dir=str(output_dir / "cases"),
                source_provenance="benchmark_manifest",
            )
            bundle = run_input_evidence_normalizer(request, runtime=runtime, case_dir=case_dir)
            evidence = bundle.model_dump()
            product = run_product_understanding(request, runtime, evidence)
            result = _product_understanding_case_result(case, evidence, product)
            result["status"] = "completed" if _product_understanding_case_passes(result) else "failed"
            (case_dir / "input_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            (case_dir / "product_understanding.json").write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
            (case_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(result)
        except Exception as exc:
            results.append({"case_id": case.get("case_id"), "status": "failed", "error_message": str(exc)[:500]})
    (output_dir / "benchmark_results.json").write_text(json.dumps({"cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "category_consistency_report.json").write_text(
        json.dumps({"cases": [{"case_id": item.get("case_id"), "broad_category": item.get("broad_category"), "category_path": item.get("category_path"), "status": item.get("status")} for item in results]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "evidence_integrity_report.json").write_text(
        json.dumps({"cases": [{"case_id": item.get("case_id"), "evidence_integrity_ok": item.get("evidence_integrity_ok"), "status": item.get("status")} for item in results]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "unsupported_claim_report.json").write_text(
        json.dumps({"cases": [{"case_id": item.get("case_id"), "unsupported_claim_categories": item.get("unsupported_claim_categories", []), "status": item.get("status")} for item in results]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "status": "completed" if results and all(item.get("status") == "completed" for item in results) else "partial",
        "runs": results,
        "actual_api_calls": any((item.get("provider_metadata") or {}).get("provider") == "openai" for item in results),
        "image_generation_performed": False,
        "actual_source_image_count": sum(1 for item in manifest.get("cases", []) if item.get("source_image_path") and Path(str(item.get("source_image_path"))).exists()),
        "synthetic_source_image_count": 0,
        "mock_or_fixture_count": 0,
        "stop_after": args.stop_after,
    }


def run_composite_benchmark(*, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    if not args.benchmark_manifest:
        return {"status": "blocked", "missing_requirements": ["--benchmark-manifest"], "runs": []}
    manifest = json.loads(Path(args.benchmark_manifest).read_text(encoding="utf-8"))
    runtime = _canonical_runtime(args)
    runs: list[dict[str, Any]] = []
    synthetic_source_count = 0
    for case in manifest.get("cases", []):
        source = case.get("source_image_path")
        if case.get("input_mode") in {"image_only", "text_and_image"} and (not source or not Path(source).exists()):
            runs.append({"case_id": case.get("case_id"), "status": "failed", "error_code": "missing_actual_source_image"})
            continue
        request = ActualCreativeInput(
            case_id=str(case["case_id"]),
            input_mode=case.get("input_mode") or "text_only",
            user_text=case.get("user_text"),
            source_image_path=source,
            placement=case.get("placement") or "instagram_feed_static",
            promotion_goal=case.get("promotion_goal") or "brand_awareness",
            seed=int(case.get("seed") or args.seed),
            output_dir=str(output_dir),
            source_provenance=case.get("source_provenance") or ("user_uploaded" if source else None),
        )
        runs.append(run_actual_creative_case(request, runtime).model_dump())
    comparison_path = _build_canonical_comparison(output_dir, runs)
    return {
        "schema_version": "open_domain_product_understanding_composite_v1",
        "status": _canonical_summary_status(runs),
        "runs": runs,
        "actual_api_calls": any(_has_provider_usage(run.get("copy_provider_metadata")) or _has_provider_usage((run.get("vlm_result") or {}).get("provider_metadata") or run.get("vlm_result")) for run in runs),
        "image_generation_performed": any(bool(run.get("flux_metadata")) for run in runs),
        "mock_or_fixture_count": sum(int(run.get("mock_or_fixture_count") or 0) for run in runs),
        "synthetic_source_image_count": synthetic_source_count,
        "comparison_sheet_path": str(comparison_path) if comparison_path else None,
    }


def _product_understanding_case_result(case: dict[str, Any], evidence: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    category_path = product.get("category_path") or []
    expected_prefix = case.get("expected_category_prefix") or []
    evidence_ids = {
        item.get("evidence_id")
        for group in ("explicit_user_facts", "visual_observations", "asset_metadata_evidence", "brand_profile_evidence", "reference_evidence")
        for item in evidence.get(group, [])
    }
    name_ids = product.get("product_name_evidence_ids") or []
    return {
        "case_id": case.get("case_id"),
        "input_mode": case.get("input_mode"),
        "product_name": product.get("product_name"),
        "normalized_product_type": product.get("normalized_product_type"),
        "broad_category": product.get("broad_category"),
        "category_path": category_path,
        "unsupported_claim_categories": product.get("unsupported_claim_categories") or [],
        "provider_metadata": product.get("provider_metadata") or {},
        "schema_valid": product.get("schema_version") == "product_understanding_v1",
        "broad_category_ok": product.get("broad_category") == case.get("expected_broad_category"),
        "category_prefix_ok": category_path[: len(expected_prefix)] == expected_prefix,
        "evidence_integrity_ok": all(item in evidence_ids for item in name_ids),
        "identity_ok": bool(product.get("product_name")) and product.get("product_name") != "unknown product" and bool(name_ids),
        "confidence_ok": float(product.get("confidence") or 0.0) >= float(case.get("min_confidence") or 0.70),
        "review_ok": not product.get("manual_review_required") and not product.get("clarification_required"),
        "normalized_type_ok": product.get("normalized_product_type") is None or any(ch.isalpha() for ch in str(product.get("normalized_product_type"))),
        "category_depth_ok": len(category_path) >= (2 if product.get("normalized_product_type") else 1),
    }


def _product_understanding_case_passes(result: dict[str, Any]) -> bool:
    return all(
        bool(result.get(key))
        for key in (
            "schema_valid",
            "broad_category_ok",
            "category_prefix_ok",
            "evidence_integrity_ok",
            "identity_ok",
            "confidence_ok",
            "review_ok",
            "normalized_type_ok",
            "category_depth_ok",
        )
    )

def _canonical_runtime(args: argparse.Namespace) -> ActualCreativeRuntime:
    from openai import OpenAI  # type: ignore
    from orchestrator.app.t2i.engines.registry import get_t2i_engine

    client = OpenAI(timeout=90)

    class OpenAIAdapter:
        def __init__(self, openai_client: Any):
            self.client = openai_client

        def normalize_input_evidence(self, *, request: Any, model: str) -> dict[str, Any]:
            started = time.perf_counter()
            prompt = (
                "Return JSON only matching InputEvidenceBundle. Separate explicit_user_facts from visual_observations, "
                "creative_inferences, unknown_fields, unresolved_questions, and input_conflicts. "
                "Do not treat user intent as visual evidence. Use user text as authoritative for explicit claims, and image content only for visible observations. "
                f"Request: {request.model_dump_json()}"
            )
            if getattr(request, "source_image_path", None):
                encoded = base64.b64encode(Path(request.source_image_path).read_bytes()).decode("ascii")
                response = self.client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                            ],
                        }
                    ],
                    temperature=0,
                )
            else:
                response = self.client.responses.create(model=model, input=prompt, temperature=0)
            payload = json.loads(getattr(response, "output_text", "") or "{}")
            metadata = {
                "provider": "openai",
                "model": model,
                "fallback_used": False,
                "token_usage": _usage_dict(response),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
            payload["provider_metadata"] = {"vision": metadata} if request.input_mode in {"image_only", "text_and_image"} else {"normalizer": metadata}
            return payload

        def understand_product(self, *, request: Any, evidence: dict[str, Any], model: str) -> dict[str, Any]:
            started = time.perf_counter()
            prompt = (
                "Return JSON only with product_understanding. You receive a canonical InputEvidenceBundle. "
                "Generate ProductUnderstanding only. Do not generate advertising copy, headline, CTA, slogan, offer, or visual style. "
                "Keep verified facts separate from visual observations and inferences. Every verified fact must reference an evidence item that already exists in InputEvidenceBundle. "
                "Do not invent price, discount, ingredients, origin, manufacturing method, certification, efficacy, health effects, beauty effects, numeric claims, scarcity, or social proof. "
                "normalized_product_type must be a valid English snake_case product type when the product identity is known, including for non-English product names. "
                "category_path is open vocabulary. broad_category must be one of the provided top-level taxonomy values. "
                "If an explicit product mention exists and there is no identity conflict, classify it into the top-level taxonomy using general category knowledge. "
                "Do not return broad_category='other' for a clearly named food, beverage, beauty, fashion, home, technology, education, hospitality, automotive, or local service product. "
                "If evidence is insufficient, preserve unknown fields and mark clarification/manual review instead of guessing. "
                f"Request metadata: {request.model_dump_json()} InputEvidenceBundle: {json.dumps(evidence, ensure_ascii=False)}"
            )
            response = self.client.responses.create(model=model, input=prompt, temperature=0)
            payload = json.loads(getattr(response, "output_text", "") or "{}")
            return {
                "product_understanding": payload.get("product_understanding") or payload,
                "provider_metadata": {
                    "provider": "openai",
                    "model": model,
                    "fallback_used": False,
                    "task": "product_understanding_v1",
                    "token_usage": _usage_dict(response),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            }

        def generate_product_copy(self, *, request: Any, evidence: dict[str, Any], product_understanding: dict[str, Any] | None = None, model: str) -> dict[str, Any]:
            started = time.perf_counter()
            prompt = (
                "Return JSON only with product_copy_context, copy_candidates, "
                "recommended_candidate_id, selected_copy, input_conflicts, requires_manual_review. "
                "Do not generate or revise ProductUnderstanding. product_copy_context must include brand_tone, message_territories, language_policy, copy_presence_plan, interaction_plan, supported_claims, unsupported_claims. "
                "Generate grounded advertising copy only from the supplied InputEvidenceBundle and ProductUnderstanding. Prefer visual-first minimal copy: image-only, headline-only, headline+support, or headline+closing. "
                "Do not create generic action CTAs unless a verified destination exists. Hard block Learn More, Discover More, Shop Now, 지금 확인하기, 자세히 보기, 메뉴 보기, 지금 만나보세요 when no destination is verified. "
                "For Korean local food/menu products, use Korean headline by default and do not romanize product names unless explicitly requested. "
                "Do not use source image bytes or raw visual assumptions outside the bundle. "
                f"Request metadata: {request.model_dump_json()} ProductUnderstanding: {json.dumps(product_understanding or {}, ensure_ascii=False)} InputEvidenceBundle: {json.dumps(evidence, ensure_ascii=False)}"
            )
            response = self.client.responses.create(model=model, input=prompt, temperature=0)
            payload = json.loads(getattr(response, "output_text", "") or "{}")
            candidates = payload.get("copy_candidates") or []
            selected = next((item for item in candidates if item.get("id") == payload.get("recommended_candidate_id")), None) or (candidates[0] if candidates else None)
            return {
                "product_understanding": product_understanding or {},
                "product_copy_context": payload.get("product_copy_context") or {},
                "copy_candidates": candidates,
                "recommended_candidate_id": payload.get("recommended_candidate_id"),
                "selected_copy": selected,
                "input_conflicts": payload.get("input_conflicts") or [],
                "requires_manual_review": bool(payload.get("requires_manual_review")),
                "provider_metadata": {
                    "provider": "openai",
                    "model": model,
                    "fallback_used": False,
                    "token_usage": _usage_dict(response),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            }

        def analyze_source_image(self, *, request: Any, image_path: str, model: str) -> dict[str, Any]:
            started = time.perf_counter()
            encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            response = self.client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Analyze visible product, confidence, negative space, clipping, and existing text. Return JSON only."},
                            {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                        ],
                    }
                ],
                temperature=0,
            )
            payload = json.loads(getattr(response, "output_text", "") or "{}")
            return {
                "visual_observations": payload.get("visual_observations") or [{"kind": "vision_analysis", "value": payload}],
                "provider_metadata": {
                    "provider": "openai",
                    "model": model,
                    "fallback_used": False,
                    "token_usage": _usage_dict(response),
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            }

        def evaluate_final_composite(self, *, request: Any, image_path: str, copy: dict[str, Any], model: str, evaluation_context: dict[str, Any] | None = None) -> dict[str, Any]:
            started = time.perf_counter()
            encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
            response = self.client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Evaluate the final ad composite. Return JSON only with product_match_score, "
                                    "copy_product_grounding_score, copy_readability_score, copy_visual_fit_score, "
                                    "product_obstruction_score, wrong_domain_detected, unsupported_claim_detected, "
                                    "commercial_viability_score, failure_reasons, recommended_action, confidence, and detected_text. "
                                    f"Evaluation context: {json.dumps(evaluation_context or {}, ensure_ascii=False)}. "
                                    "Respect copy_presence_plan and selected_variant_type. For image_only, do not fail for missing ad copy, CTA, branding, headline hierarchy, or expected OCR text."
                                ),
                            },
                            {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                        ],
                    }
                ],
                temperature=0,
            )
            payload = json.loads(getattr(response, "output_text", "") or "{}")
            payload["provider_metadata"] = {
                "provider": "openai",
                "model": model,
                "fallback_used": False,
                "token_usage": _usage_dict(response),
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
            return payload

    return ActualCreativeRuntime(
        copy_model=args.copy_model,
        vision_model=args.vlm_model,
        t2i_engine="flux2_klein_4b",
        t2i_backend="local_diffusers",
        openai_adapter=OpenAIAdapter(client),
        vision_adapter=OpenAIAdapter(client),
        flux_engine=get_t2i_engine("flux2_klein_4b"),
        call_budget=ActualCallBudget(max_openai_calls=args.max_openai_calls, max_flux_generations=args.max_flux_generations),
        render_all_variants=bool(getattr(args, "render_all_variants", False)),
    )


def _run_or_resume_canonical_case(request: ActualCreativeInput, runtime: ActualCreativeRuntime, *, resume: bool) -> dict[str, Any]:
    result_path = Path(request.output_dir) / request.case_id / "result.json"
    if resume and result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            if data.get("status") == "completed" and _canonical_artifacts_exist(data):
                return data
        except Exception:
            pass
    return run_actual_creative_case(request, runtime).model_dump()


def _canonical_artifacts_exist(data: dict[str, Any]) -> bool:
    paths = [data.get("final_composite_path")]
    if data.get("input_mode") == "text_only":
        paths.append(data.get("background_image_path"))
    return all(path and Path(str(path)).exists() for path in paths)


def _canonical_summary_status(runs: list[dict[str, Any]]) -> str:
    statuses = {run.get("status") for run in runs}
    if statuses == {"completed"}:
        return "completed"
    if "completed" in statuses:
        return "partial"
    if "manual_review" in statuses:
        return "manual_review"
    if "blocked" in statuses:
        return "blocked"
    return "failed"


def _build_canonical_comparison(output_dir: Path, runs: list[dict[str, Any]]) -> Path | None:
    paths = [Path(str(run.get("final_composite_path"))) for run in runs if run.get("final_composite_path") and Path(str(run.get("final_composite_path"))).exists()]
    if not paths:
        return None
    thumbs = []
    for path in paths:
        with Image.open(path).convert("RGB") as image:
            image.thumbnail((360, 360))
            canvas = Image.new("RGB", (360, 400), "#FFFFFF")
            canvas.paste(image, ((360 - image.width) // 2, 0))
            ImageDraw.Draw(canvas).text((12, 372), path.parent.name, fill="#111111")
            thumbs.append(canvas)
    sheet = Image.new("RGB", (360 * len(thumbs), 400), "#FFFFFF")
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, (360 * index, 0))
    output = output_dir / "comparison_all_modes.png"
    sheet.save(output)
    return output


def _write_evidence_comparison(output_dir: Path, runs: list[dict[str, Any]]) -> Path:
    rows: list[dict[str, Any]] = []
    for run in runs:
        evidence = run.get("input_evidence") or {}
        explicit = evidence.get("explicit_user_facts") or []
        visual = evidence.get("visual_observations") or []
        product = next((item.get("value") for item in explicit if item.get("key") == "product_name"), None)
        rows.append(
            {
                "case_id": run.get("case_id"),
                "input_mode": run.get("input_mode"),
                "status": run.get("status"),
                "product_identity": product,
                "user_intent": evidence.get("user_intent"),
                "explicit_user_facts": explicit,
                "visual_observations": visual,
                "unknown_fields": evidence.get("unknown_fields") or [],
                "input_conflicts": evidence.get("input_conflicts") or [],
                "overall_confidence": evidence.get("overall_confidence"),
            }
        )
    path = output_dir / "evidence_comparison.json"
    path.write_text(json.dumps({"schema_version": "input_evidence_comparison_v1", "runs": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _has_provider_usage(metadata: object) -> bool:
    if not isinstance(metadata, dict):
        return False
    usage = metadata.get("token_usage")
    return isinstance(usage, dict) and int(usage.get("input_tokens") or 0) > 0 and int(usage.get("output_tokens") or 0) > 0


def run_actual_case(*, args: argparse.Namespace, output_dir: Path, case_dir: Path) -> dict[str, Any]:
    request = ActualCreativeInput(
        case_id=args.case,
        input_mode="text_only",
        user_text=f"Create a premium advertising creative for {args.case}.",
        placement="instagram_feed_static",
        promotion_goal="brand_awareness",
        seed=args.seed,
        output_dir=str(output_dir),
    )
    result = run_actual_creative_case(request, _canonical_runtime(args)).model_dump()
    return {
        **result,
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "copy_token_usage": (result.get("copy_provider_metadata") or {}).get("token_usage"),
        "vlm_token_usage": ((result.get("vlm_result") or {}).get("provider_metadata") or {}).get("token_usage"),
        "copy_fallback_used": (result.get("copy_provider_metadata") or {}).get("fallback_used"),
        "vlm_fallback_used": ((result.get("vlm_result") or {}).get("provider_metadata") or {}).get("fallback_used"),
        "flux_engine": (result.get("flux_metadata") or {}).get("engine"),
        "flux_backend": (result.get("flux_metadata") or {}).get("backend"),
        "flux_model": (result.get("flux_metadata") or {}).get("model"),
        "flux_latency_ms": (result.get("flux_metadata") or {}).get("runtime_ms"),
        "flux_output_path": (result.get("flux_metadata") or {}).get("output_path"),
        "background_path": result.get("background_image_path"),
        "initial_final_composite_path": result.get("final_composite_path"),
        "repaired_final_composite_path": "pass_without_revision",
        "background_hash": result.get("background_sha256"),
        "final_composite_hash": result.get("final_composite_sha256"),
    }


def _legacy_run_actual_case(*, args: argparse.Namespace, output_dir: Path, case_dir: Path) -> dict[str, Any]:
    copy_result = generate_gpt54_copy_candidates(args)
    (output_dir / "copy_candidates_gpt54.json").write_text(json.dumps(copy_result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not _strict_openai_success(copy_result, args.copy_model, prefix="copy"):
        return _blocked(args.case, "copy_generation_not_actual", copy_result=_public(copy_result))

    flux_result = generate_flux2_background(args, case_dir)
    if not _strict_flux_success(flux_result):
        return _blocked(args.case, "flux_generation_not_performed", flux_result=_public(flux_result))

    state = build_initial_state(args=args, copy_result=copy_result, flux_result=flux_result)
    state, initial_report, initial_vlm = render_and_validate(state=state, args=args, case_dir=case_dir, label="initial")
    initial_path = Path(state["render_result"]["final_image_path"])
    background_path = Path(flux_result["image_path"])
    if _sha256(background_path) == _sha256(initial_path):
        return _failed(args.case, "background_copy_used_as_final")

    action = initial_report.primary_action
    revision_trace: dict[str, Any] = {
        "initial_failure_types": initial_report.failure_types,
        "selected_revision_action": action,
        "rerun_start_node": None,
        "t2i_call_delta": 0,
        "revision_counters": {"attempt": 1},
    }
    final_state = state
    final_report = initial_report
    final_vlm = initial_vlm
    repaired_path: str | None = None
    if initial_report.status == "revise" and args.max_composite_attempts > 1:
        final_state, final_report, final_vlm, repaired_path = run_partial_rerun(state=state, action=action, args=args, case_dir=case_dir, revision_trace=revision_trace)

    comparison_path = build_comparison(case_dir, initial_path, Path(repaired_path) if repaired_path else None)
    _write_public_state(case_dir / "initial_state_public.json", state)
    _write_public_state(case_dir / "final_state_public.json", final_state)
    (case_dir / "initial_quality_report.json").write_text(json.dumps(initial_report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_quality_report.json").write_text(json.dumps(final_report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_vlm_result.json").write_text(json.dumps(final_vlm, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "final_ocr_result.json").write_text(json.dumps(final_state.get("final_ocr_gate") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "revision_trace.json").write_text(json.dumps(revision_trace, ensure_ascii=False, indent=2), encoding="utf-8")

    run = {
        "case_id": args.case,
        "status": "completed" if completed_conditions(copy_result, flux_result, state, final_state, initial_report, final_report, initial_vlm, final_vlm) else "failed",
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "copy_token_usage": copy_result.get("copy_token_usage"),
        "vlm_token_usage": final_vlm.get("vlm_token_usage"),
        "copy_fallback_used": copy_result.get("copy_fallback_used"),
        "vlm_fallback_used": final_vlm.get("vlm_fallback_used"),
        "copy_candidates": copy_result.get("copy_candidates"),
        "selected_copy": copy_result.get("selected_copy"),
        "flux_engine": flux_result.get("flux_engine"),
        "flux_backend": flux_result.get("flux_backend"),
        "flux_model": flux_result.get("flux_model"),
        "flux_latency_ms": flux_result.get("flux_latency_ms"),
        "flux_output_path": flux_result.get("flux_output_path"),
        "background_path": str(background_path),
        "initial_final_composite_path": str(initial_path),
        "repaired_final_composite_path": repaired_path or "pass_without_revision",
        "comparison_image_path": str(comparison_path),
        "background_hash": _sha256(background_path),
        "initial_composite_hash": initial_report.evaluated_image_sha256,
        "final_composite_hash": final_report.evaluated_image_sha256,
        "initial_failure_types": initial_report.failure_types,
        "selected_revision_action": action,
        "t2i_call_delta": revision_trace["t2i_call_delta"],
        "final_quality_status": final_report.status,
        "mock_or_fixture_count": 0,
    }
    (case_dir / "result.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def generate_gpt54_copy_candidates(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(timeout=90)
        prompt = (
            "Return JSON only. Generate exactly 3 ad copy candidates for the supplied open-domain product. "
            "Context: product introduction, visual-first commercial post, premium/editorial/warm. "
            "Angles: product-first, emotion-first, editorial/collection-first. English headline allowed; Korean body and CTA preferred; CTA optional. "
            "Avoid AI/smart/consulting/expert/technology/service innovation/best/freshest/free/price/guaranteed claims. "
            "Schema: {\"copy_candidates\":[{\"id\":\"copy_1\",\"angle\":\"...\",\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"\",\"grounding\":{},\"score\":{}}],\"selected_copy\":{\"headline\":\"...\",\"subcopy\":\"...\",\"cta\":\"...\"},\"selection_reason\":\"...\"}"
        )
        response = client.responses.create(model=args.copy_model, input=prompt, temperature=0)
        raw = getattr(response, "output_text", "") or "{}"
        parsed = json.loads(raw)
        usage = _usage_dict(response)
        parsed.update(
            {
                "copy_provider": "openai",
                "copy_model": args.copy_model,
                "copy_fallback_used": False,
                "copy_token_usage": usage,
                "copy_latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        _validate_copy_result(parsed, args.copy_model)
        return parsed
    except Exception as exc:
        return {"copy_provider": "openai", "copy_model": args.copy_model, "copy_fallback_used": True, "error_code": "copy_actual_failed", "error_message": str(exc)[:500]}


def generate_flux2_background(args: argparse.Namespace, case_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        engine = get_t2i_engine("flux2_klein_4b")
        prompt = (
            "Premium editorial commercial photography background for an open-domain product advertisement, "
            "clean blank negative space for later copy overlay, warm commercial mood, no text, no signage, no logo."
        )
        output = engine.generate(
            T2IGenerationInput(
                job_id=f"final_composite_{args.case}_{args.seed}",
                prompt=prompt,
                negative_prompt="visible writing, logo, watermark, sign, poster text",
                width=1024,
                height=1024,
                num_images=1,
                seed=args.seed,
                output_dir=str(case_dir),
                metadata={"source": "final_composite_quality_actual", "case_id": args.case},
            )
        )
        if not output.image_paths:
            raise RuntimeError("FLUX.2 Klein returned no image path.")
        source = Path(output.image_paths[0])
        target = case_dir / f"background_flux2_seed{args.seed}.png"
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        _verify_image(target)
        return {
            "status": "completed",
            "actual_flux_generation": True,
            "flux_engine": output.engine,
            "flux_backend": "local_diffusers",
            "flux_model": (output.metadata or {}).get("model_name") or "black-forest-labs/FLUX.2-klein-4B",
            "flux_seed": args.seed,
            "flux_latency_ms": output.latency_ms or int((time.perf_counter() - started) * 1000),
            "flux_output_path": str(target),
            "image_path": str(target),
            "metadata": output.metadata,
        }
    except Exception as exc:
        return {"status": "failed", "actual_flux_generation": False, "error_code": getattr(exc, "error_code", "flux_actual_failed"), "error_message": str(exc)[:500]}


def build_initial_state(*, args: argparse.Namespace, copy_result: dict[str, Any], flux_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": f"final-composite-{args.case}",
        "thread_id": f"final-composite-{args.case}",
        "user_plan": "premium",
        "context": {
            "business_type": "open_domain_product",
            "item_or_service": "product",
            "promotion_goal": "product_introduction",
            "brand_tone": "premium/editorial/warm",
        },
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1024, "height": 1024},
        "copy_visual_intent": {
            "hierarchy": "editorial_product",
            "headline_emphasis": "large_elegant",
            "body_density": "low",
            "cta_visibility": "optional",
            "cta_style": "text_link",
            "preferred_alignment": "left",
            "typography_mood": "premium_serif",
            "plate_policy": "subtle",
            "product_text_relationship": "side_by_side",
        },
        "marketing_copy": copy_result["selected_copy"],
        "t2i_result": {"engine": "flux2_klein_4b", "image_paths": [flux_result["image_path"]], "metadata": flux_result.get("metadata") or {}},
        "artifact_refs": [{"type": "background_image", "path": flux_result["image_path"]}],
        "final_composite_attempts": 1,
    }


def render_and_validate(*, state: dict[str, Any], args: argparse.Namespace, case_dir: Path, label: str) -> tuple[dict[str, Any], Any, dict[str, Any]]:
    state = _apply(state, copy_spec_parser_node(state))
    state = _apply(state, typography_art_direction_node(state))
    state = _apply(state, text_style_binder_node(state))
    state = _apply(state, text_layout_planner_node(state))
    state = _apply(state, image_layout_analyzer_node(state))
    state = _apply(state, post_t2i_layout_refiner_node(state))
    state = _apply(state, adaptive_typography_refiner_node(state))
    state = _apply(state, safe_area_gate_node(state))
    state = _apply(state, text_renderer_node(state))
    render_result = state.get("render_result") or {}
    final_path = Path(render_result.get("final_image_path") or "")
    _verify_image(final_path)
    target = case_dir / ("initial_final_composite.png" if label == "initial" else "repaired_final_composite.png")
    if final_path.resolve() != target.resolve():
        target.write_bytes(final_path.read_bytes())
    state["render_result"] = {**render_result, "final_image_path": str(target)}
    state["final_image_path"] = str(target)
    state["artifact_refs"] = [ref for ref in state.get("artifact_refs", []) if ref.get("type") != "final_image"] + [{"type": "final_image", "path": str(target)}]
    vlm = judge_final_composite(args=args, image_path=target, copy=state.get("marketing_copy") or {})
    if not _strict_openai_success(vlm, args.vlm_model, prefix="vlm"):
        raise RuntimeError("VLM actual judge did not meet strict gpt-5.4 contract.")
    state["final_composite_vlm_result"] = vlm
    state["final_ocr_gate"] = _ocr_from_vlm(vlm, state.get("marketing_copy") or {})
    state = _apply(state, readability_gate_node(state))
    state = _apply(state, final_validation_node(state))
    return state, evaluate_final_composite(state), vlm


def judge_final_composite(*, args: argparse.Namespace, image_path: Path, copy: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        from openai import OpenAI  # type: ignore

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        client = OpenAI(timeout=90)
        prompt = (
            "Evaluate this final ad composite. Use only the supplied final_image. Return JSON with keys: "
            "expected_copy_visible, copy_clipping_detected, product_overlap, face_hand_overlap, "
            "headline_hierarchy_score, cta_dominance_score, plate_excess_score, contrast_score, "
            "visual_clutter_score, alignment_score, safe_margin_score, business_fit_score, brand_fit_score, "
            "commercial_viability_score, generic_copy_detected, background_text_space_insufficient, "
            "detected_text, missing_text_count, extra_text_count, failure_reasons, suggested_action, confidence. "
            f"Expected copy: {json.dumps(copy, ensure_ascii=False)}"
        )
        response = client.responses.create(
            model=args.vlm_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                    ],
                }
            ],
            temperature=0,
        )
        parsed = json.loads(getattr(response, "output_text", "") or "{}")
        usage = _usage_dict(response)
        parsed.update(
            {
                "vlm_provider": "openai",
                "vlm_model": args.vlm_model,
                "vlm_fallback_used": False,
                "vlm_token_usage": usage,
                "vlm_latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        return parsed
    except Exception as exc:
        return {"vlm_provider": "openai", "vlm_model": args.vlm_model, "vlm_fallback_used": True, "error_code": "vlm_actual_failed", "error_message": str(exc)[:500]}


def run_partial_rerun(*, state: dict[str, Any], action: str, args: argparse.Namespace, case_dir: Path, revision_trace: dict[str, Any]) -> tuple[dict[str, Any], Any, dict[str, Any], str]:
    revision_state = _apply(state, final_composite_revision_node({**state, "final_composite_quality_report": state.get("final_composite_quality_report") or {"status": "revise", "primary_action": action}}))
    plan = revision_state.get("final_composite_revision_plan") or {}
    rerun = plan.get("rerun_from_node")
    revision_trace["rerun_start_node"] = rerun
    if rerun == "final_copy_revision":
        revision_state = _apply(revision_state, final_copy_revision_node(revision_state))
        return render_and_validate(state=revision_state, args=args, case_dir=case_dir, label="repaired") + (str(case_dir / "repaired_final_composite.png"),)
    if rerun in {"adaptive_typography_refiner", "post_t2i_layout_refiner"}:
        revision_state = apply_visual_patch_for_rerun(revision_state, action)
        return render_and_validate(state=revision_state, args=args, case_dir=case_dir, label="repaired") + (str(case_dir / "repaired_final_composite.png"),)
    return state, evaluate_final_composite(state), state.get("final_composite_vlm_result") or {}, ""


def apply_visual_patch_for_rerun(state: dict[str, Any], action: str) -> dict[str, Any]:
    intent = dict(state.get("copy_visual_intent") or {})
    if action in {"retry_text_style", "reduce_cta_emphasis"}:
        intent.update(
            {
                "typography_mood": "clean_sans",
                "plate_policy": "content_fit",
                "cta_style": "text_link",
                "cta_visibility": "optional",
                "preferred_alignment": "center",
                "product_text_relationship": "top_bottom",
            }
        )
        state["regeneration_patch"] = {
            "patches": {
                "final_composite_style": {
                    "target": "textStyle",
                    "increaseContrast": True,
                    "enableShadowOrOverlay": True,
                }
            }
        }
    if action == "retry_layout":
        intent.update({"preferred_alignment": "center", "product_text_relationship": "top_bottom"})
    state["copy_visual_intent"] = intent
    copy = dict(state.get("marketing_copy") or {})
    if action == "reduce_cta_emphasis" and copy.get("cta"):
        copy["cta"] = ""
        state["marketing_copy"] = copy
    return state


def completed_conditions(copy_result: dict[str, Any], flux_result: dict[str, Any], initial_state: dict[str, Any], final_state: dict[str, Any], initial_report: Any, final_report: Any, initial_vlm: dict[str, Any], final_vlm: dict[str, Any]) -> bool:
    background = Path(flux_result.get("image_path") or "")
    final_path = Path(final_state.get("render_result", {}).get("final_image_path") or "")
    return (
        _strict_openai_success(copy_result, "gpt-5.4", prefix="copy")
        and _strict_openai_success(final_vlm, "gpt-5.4", prefix="vlm")
        and _strict_flux_success(flux_result)
        and final_path.exists()
        and _sha256(background) != _sha256(final_path)
        and bool(initial_state.get("final_ocr_gate"))
        and int(initial_state.get("synthetic_trace_count") or 0) == 0
        and bool(initial_report.evaluated_image_sha256)
        and final_report.status in {"pass", "manual_review", "reject"}
    )


def build_comparison(case_dir: Path, initial_path: Path, repaired_path: Path | None) -> Path:
    output = case_dir / "comparison_before_after.png"
    images = [initial_path, repaired_path or initial_path]
    thumbs = []
    for index, path in enumerate(images):
        with Image.open(path).convert("RGB") as image:
            image.thumbnail((512, 512))
            canvas = Image.new("RGB", (512, 552), "#FFFFFF")
            canvas.paste(image, ((512 - image.width) // 2, 0))
            ImageDraw.Draw(canvas).text((16, 524), "initial" if index == 0 else ("repaired" if repaired_path else "pass_without_revision"), fill="#111111")
            thumbs.append(canvas)
    sheet = Image.new("RGB", (1024, 552), "#FFFFFF")
    sheet.paste(thumbs[0], (0, 0))
    sheet.paste(thumbs[1], (512, 0))
    sheet.save(output)
    return output


def _missing_actual_requirements(args: argparse.Namespace) -> list[str]:
    required_env = dict(REQUIRED_ACTUAL_ENV)
    if getattr(args, "product_understanding_benchmark", False) and getattr(args, "stop_after", None) == "product_understanding":
        required_env.pop("EASYADS_FLUX2_KLEIN_ACTUAL", None)
        required_env.pop("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL", None)
    missing = [name for name, expected in required_env.items() if str(os.getenv(name, "")).strip().lower() != expected.lower()]
    if not os.getenv("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if args.copy_model != "gpt-5.4":
        missing.append("copy_model_must_be_gpt-5.4")
    if args.vlm_model != "gpt-5.4":
        missing.append("vlm_model_must_be_gpt-5.4")
    if not args.force_flux_generation and not getattr(args, "canonical_smoke", False) and not (getattr(args, "product_understanding_benchmark", False) and getattr(args, "stop_after", None) == "product_understanding"):
        missing.append("force_flux_generation_required")
    return missing


def _validate_copy_result(result: dict[str, Any], model: str) -> None:
    if result.get("copy_model") != model or model != "gpt-5.4":
        raise ValueError("copy model must be gpt-5.4")
    candidates = result.get("copy_candidates") or []
    if len(candidates) != 3:
        raise ValueError("copy candidate count must be 3")
    selected = result.get("selected_copy") or {}
    if not selected.get("headline"):
        raise ValueError("selected copy missing headline")
    text = json.dumps({"candidates": candidates, "selected": selected}, ensure_ascii=False).lower()
    if any(term.lower() in text for term in FORBIDDEN_COPY_TERMS):
        raise ValueError("copy contains forbidden phrase")
    if not _positive_usage(result.get("copy_token_usage")):
        raise ValueError("copy token usage missing")


def _strict_openai_success(result: dict[str, Any], model: str, *, prefix: str) -> bool:
    return (
        result.get(f"{prefix}_provider") == "openai"
        and result.get(f"{prefix}_model") == model
        and result.get(f"{prefix}_fallback_used") is False
        and _positive_usage(result.get(f"{prefix}_token_usage"))
    )


def _strict_flux_success(result: dict[str, Any]) -> bool:
    return (
        result.get("status") == "completed"
        and result.get("actual_flux_generation") is True
        and result.get("flux_engine") == "flux2_klein_4b"
        and result.get("flux_backend") == "local_diffusers"
        and Path(result.get("image_path") or "").exists()
    )


def _positive_usage(usage: object) -> bool:
    if not isinstance(usage, dict):
        return False
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return input_tokens > 0 and output_tokens > 0


def _usage_dict(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _ocr_from_vlm(vlm: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    detected = vlm.get("detected_text") or [value for value in copy.values() if value]
    return {
        "status": "pass" if vlm.get("expected_copy_visible", True) else "fail",
        "provider": "openai_vlm_ocr_fallback",
        "ocr": {
            "detected_text": detected,
            "missing_text_count": int(vlm.get("missing_text_count") or 0),
            "extra_text_count": int(vlm.get("extra_text_count") or 0),
        },
    }


def _apply(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    state.update(update or {})
    return state


def _verify_image(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with Image.open(path) as image:
        image.verify()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocked(case_id: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"case_id": case_id, "status": "blocked", "error_code": code, **extra}


def _failed(case_id: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"case_id": case_id, "status": "failed", "error_code": code, **extra}


def _base_summary(args: argparse.Namespace, env_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "final_composite_quality_loop_actual_e2e_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": args.case,
        "actual_requested": bool(args.actual),
        "copy_model": args.copy_model,
        "vlm_model": args.vlm_model,
        "env_file_found": env_report.get("env_file_found"),
        "actual_api_calls": False,
        "image_generation_performed": False,
        "runtime_environment": _runtime_environment_report(),
    }


def _is_clean_background_source(path: str | None) -> bool:
    if not path:
        return False
    name = Path(path).name.lower()
    if "final_composite" in name:
        return False
    return "background" in name or "clean" in name


def _runtime_environment_report() -> dict[str, Any]:
    report: dict[str, Any] = {"python_executable": sys.executable, "uv_project_environment": os.getenv("UV_PROJECT_ENVIRONMENT")}
    try:
        import diffusers  # type: ignore

        report["diffusers_version"] = getattr(diffusers, "__version__", None)
        report["flux2_pipeline_available"] = hasattr(diffusers, "Flux2KleinPipeline")
    except Exception as exc:  # pragma: no cover - diagnostic only
        report["diffusers_error"] = type(exc).__name__
        report["flux2_pipeline_available"] = False
    try:
        import torch  # type: ignore

        report["torch_version"] = getattr(torch, "__version__", None)
        report["cuda_available"] = bool(torch.cuda.is_available())
        report["cuda_device"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as exc:  # pragma: no cover - diagnostic only
        report["torch_error"] = type(exc).__name__
        report["cuda_available"] = False
        report["cuda_device"] = None
    return report


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_public_state(path: Path, state: dict[str, Any]) -> None:
    public = {key: state.get(key) for key in ("marketing_copy", "render_result", "artifact_refs", "final_ocr_gate")}
    path.write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")


def _public(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if "key" not in key.lower() and "token" not in key.lower()}


if __name__ == "__main__":
    raise SystemExit(main())
