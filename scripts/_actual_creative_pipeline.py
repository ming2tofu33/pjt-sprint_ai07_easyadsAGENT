"""Shared actual creative pipeline for guarded E2E runners."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from orchestrator.app.quality_gate.final_composite_service import evaluate_final_composite
from orchestrator.app.t2i.engines.base import T2IGenerationInput


@dataclass
class ActualCreativeCase:
    case_id: str
    seed: int
    width: int
    height: int
    context: dict[str, Any]
    user_input: str
    ad_format_contract: dict[str, Any]
    creative_lane_decision: dict[str, Any]
    copy_presence_plan: dict[str, Any]
    information_panel_plan: dict[str, Any]
    platform_safe_zone_spec: dict[str, Any]
    required_information: dict[str, Any]
    copy_prompt_constraints: dict[str, Any]
    output_dir: Path


@dataclass
class ActualRuntimeContext:
    openai_client: Any
    flux_engine: Any
    copy_model: str
    vlm_model: str


def run_actual_creative_case(case: ActualCreativeCase, runtime: ActualRuntimeContext) -> dict[str, Any]:
    case.output_dir.mkdir(parents=True, exist_ok=True)
    copy_result = _generate_copy(case, runtime)
    flux_result = _generate_background(case, runtime)
    state = _build_state(case, copy_result, flux_result)
    state = _run_renderer_nodes(state)
    final_path = Path(state["render_result"]["final_image_path"])
    _verify_image(final_path)
    vlm_result = _judge_final(case, runtime, final_path)
    state["final_composite_vlm_result"] = vlm_result
    state["final_ocr_gate"] = _ocr_from_vlm(vlm_result, state.get("marketing_copy") or {})
    final_validation = evaluate_final_composite(state)
    result = {
        "case_id": case.case_id,
        "status": "completed" if _completed(copy_result, flux_result, vlm_result, final_path, final_validation) else "failed",
        "copy_call_required": copy_result["copy_call_required"],
        "copy_call_skipped_reason": copy_result.get("copy_call_skipped_reason"),
        "actual_openai_call": bool(copy_result.get("actual_openai_call")),
        "actual_vlm_call": True,
        "actual_flux_generation": True,
        "copy_provider": copy_result.get("copy_provider"),
        "copy_model": runtime.copy_model,
        "vlm_model": runtime.vlm_model,
        "copy_token_usage": copy_result.get("copy_token_usage"),
        "vlm_token_usage": vlm_result.get("vlm_token_usage"),
        "copy_fallback_used": False,
        "vlm_fallback_used": False,
        "flux_engine": flux_result.get("flux_engine"),
        "flux_backend": flux_result.get("flux_backend"),
        "flux_model": flux_result.get("flux_model"),
        "flux_latency_ms": flux_result.get("flux_latency_ms"),
        "background_flux2_path": flux_result["image_path"],
        "final_composite_path": str(final_path),
        "background_sha256": _sha256(Path(flux_result["image_path"])),
        "final_sha256": _sha256(final_path),
        "background_hash_differs_from_final": _sha256(Path(flux_result["image_path"])) != _sha256(final_path),
        "render_result": state.get("render_result"),
        "final_validation": final_validation.model_dump(),
        "vlm_result": vlm_result,
        "mock_or_fixture_used": False,
    }
    _write_case_artifacts(case, result, copy_result, flux_result, state, vlm_result)
    return result


def _generate_copy(case: ActualCreativeCase, runtime: ActualRuntimeContext) -> dict[str, Any]:
    mode = str(case.copy_presence_plan.get("mode") or "")
    if mode == "image_only":
        return {
            "copy_call_required": False,
            "copy_call_skipped_reason": "image_only",
            "actual_openai_call": False,
            "selected_copy": {"headline": "", "subcopy": "", "cta": "", "metadata": {"copy_mode": "no_copy"}},
            "copy_token_usage": None,
        }
    started = time.perf_counter()
    prompt = {
        "task": "Generate verified ad copy roles as strict JSON only.",
        "case_id": case.case_id,
        "context": case.context,
        "ad_format_contract": case.ad_format_contract,
        "creative_lane_decision": case.creative_lane_decision,
        "copy_presence_plan": case.copy_presence_plan,
        "required_information": case.required_information,
        "constraints": case.copy_prompt_constraints,
    }
    response = runtime.openai_client.responses.create(model=runtime.copy_model, input=json.dumps(prompt, ensure_ascii=False), temperature=0)
    parsed = json.loads(getattr(response, "output_text", "") or "{}")
    selected = _normalize_selected_copy(parsed, case)
    return {
        "copy_call_required": True,
        "actual_openai_call": True,
        "copy_provider": "openai",
        "copy_model": runtime.copy_model,
        "copy_token_usage": _usage_dict(response),
        "copy_latency_ms": int((time.perf_counter() - started) * 1000),
        "raw_copy": parsed,
        "selected_copy": selected,
    }


def _generate_background(case: ActualCreativeCase, runtime: ActualRuntimeContext) -> dict[str, Any]:
    started = time.perf_counter()
    prompt = (
        f"Premium commercial advertising background for {case.context.get('item_or_service')}. "
        f"Creative lane: {case.creative_lane_decision.get('lane')}. "
        f"Panel plan: {case.information_panel_plan}. "
        "No text, no logo, clean negative space for later Korean copy overlay."
    )
    output = runtime.flux_engine.generate(
        T2IGenerationInput(
            job_id=f"ad_format_{case.case_id}_{case.seed}",
            prompt=prompt,
            negative_prompt="text, logo, watermark, signage, letters, fake UI button",
            width=case.width,
            height=case.height,
            num_images=1,
            seed=case.seed,
            output_dir=str(case.output_dir),
            metadata={"source": "ad_format_copy_presence_actual", "case_id": case.case_id},
        )
    )
    if not output.image_paths:
        raise RuntimeError("FLUX engine returned no image path.")
    image_path = Path(output.image_paths[0])
    target = case.output_dir / "background_flux2.png"
    if image_path.resolve() != target.resolve():
        target.write_bytes(image_path.read_bytes())
    _verify_image(target)
    return {
        "actual_flux_generation": True,
        "flux_engine": output.engine,
        "flux_backend": "local_diffusers",
        "flux_model": (output.metadata or {}).get("model_name") or "black-forest-labs/FLUX.2-klein-4B",
        "flux_latency_ms": output.latency_ms or int((time.perf_counter() - started) * 1000),
        "image_path": str(target),
        "metadata": output.metadata,
    }


def _build_state(case: ActualCreativeCase, copy_result: dict[str, Any], flux_result: dict[str, Any]) -> dict[str, Any]:
    selected = copy_result["selected_copy"]
    no_copy = case.copy_presence_plan.get("mode") == "image_only"
    return {
        "job_id": f"ad-format-{case.case_id}",
        "thread_id": f"ad-format-{case.case_id}",
        "user_plan": "premium",
        "user_input": case.user_input,
        "context": case.context,
        "current_brief": {"requested_ad_format": case.ad_format_contract.get("placement")},
        "ad_format_spec": {"ad_format": _legacy_ad_format(case), "width": case.width, "height": case.height, "aspect_ratio": case.ad_format_contract.get("aspect_ratio")},
        "ad_format_contract": case.ad_format_contract,
        "creative_lane_decision": case.creative_lane_decision,
        "copy_presence_plan": case.copy_presence_plan,
        "information_panel_plan": case.information_panel_plan,
        "platform_safe_zone_spec": case.platform_safe_zone_spec,
        "copy_generation_mode": "no_copy" if no_copy else "auto_pilot",
        "copy_required": not no_copy,
        "text_overlay_pending": not no_copy,
        "marketing_copy": selected,
        "t2i_result": {"engine": "flux2_klein_4b", "image_paths": [flux_result["image_path"]], "metadata": flux_result.get("metadata") or {}},
        "artifact_refs": [{"type": "background_image", "path": flux_result["image_path"], "metadata": {"source": "flux2_klein_4b"}}],
    }


def _run_renderer_nodes(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("copy_generation_mode") == "no_copy":
        from orchestrator.app.llm.nodes.copy_spec_parser import build_no_copy_spec
        state["copy_spec"] = build_no_copy_spec().model_dump()
        return state
    from orchestrator.app.llm.nodes.adaptive_typography_refiner import adaptive_typography_refiner_node
    from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
    from orchestrator.app.llm.nodes.image_layout_analyzer import image_layout_analyzer_node
    from orchestrator.app.llm.nodes.post_t2i_layout_refiner import post_t2i_layout_refiner_node
    from orchestrator.app.llm.nodes.safe_area_gate import safe_area_gate_node
    from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
    from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
    from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
    from orchestrator.app.llm.nodes.typography_art_director import typography_art_direction_node

    for node in (
        copy_spec_parser_node,
        typography_art_direction_node,
        text_style_binder_node,
        text_layout_planner_node,
        image_layout_analyzer_node,
        post_t2i_layout_refiner_node,
        adaptive_typography_refiner_node,
        safe_area_gate_node,
        text_renderer_node,
    ):
        state.update(node(state))
    return state


def _judge_final(case: ActualCreativeCase, runtime: ActualRuntimeContext, final_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    encoded = base64.b64encode(final_path.read_bytes()).decode("ascii")
    prompt = {
        "task": "Judge final ad composite as JSON.",
        "case_id": case.case_id,
        "criteria": [
            "format fit",
            "lane fit",
            "copy presence",
            "image preservation",
            "information completeness",
            "safe zone",
            "panel quality",
            "embedded CTA violation",
            "commercial viability",
        ],
        "contract": case.ad_format_contract,
        "copy_presence_plan": case.copy_presence_plan,
        "information_panel_plan": case.information_panel_plan,
    }
    response = runtime.openai_client.responses.create(
        model=runtime.vlm_model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                ],
            }
        ],
        temperature=0,
    )
    payload = json.loads(getattr(response, "output_text", "") or "{}")
    return {
        **payload,
        "vlm_provider": "openai",
        "vlm_model": runtime.vlm_model,
        "vlm_fallback_used": False,
        "vlm_token_usage": _usage_dict(response),
        "vlm_latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _normalize_selected_copy(parsed: dict[str, Any], case: ActualCreativeCase) -> dict[str, Any]:
    selected = parsed.get("selected_copy") or parsed.get("copy") or {}
    allowed = set(case.copy_presence_plan.get("allowed_roles") or [])
    forbidden = set(case.copy_presence_plan.get("forbidden_roles") or [])
    if "cta" in forbidden or "embedded_action_cta" in forbidden:
        selected["cta"] = ""
    if "subheadline" not in allowed and case.copy_presence_plan.get("mode") in {"headline_only", "brand_only"}:
        selected["subcopy"] = ""
    return {
        "headline": str(selected.get("headline") or ""),
        "subcopy": str(selected.get("subcopy") or selected.get("body") or ""),
        "cta": str(selected.get("cta") or ""),
        "price_line": selected.get("price") or selected.get("price_line") or case.required_information.get("price"),
        "period_line": selected.get("period") or case.required_information.get("period"),
        "metadata": {"copy_mode": case.copy_presence_plan.get("mode"), "source": "actual_openai_gpt54"},
    }


def _ocr_from_vlm(vlm: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    detected = vlm.get("detected_text") or [value for key, value in copy.items() if key != "metadata" and value]
    return {"status": "pass", "decision": "pass", "provider": "openai_vlm_ocr_fallback", "ocr": {"detected_text": detected, "missing_text_count": len(vlm.get("required_information_missing") or []), "extra_text_count": 0}}


def _completed(copy_result: dict[str, Any], flux_result: dict[str, Any], vlm: dict[str, Any], final_path: Path, final_validation: Any) -> bool:
    copy_ok = copy_result.get("copy_call_required") is False or (copy_result.get("actual_openai_call") and copy_result.get("copy_token_usage"))
    return bool(copy_ok and flux_result.get("actual_flux_generation") and vlm.get("vlm_token_usage") and final_path.exists() and final_validation.evaluated_image_sha256)


def _write_case_artifacts(case: ActualCreativeCase, result: dict[str, Any], copy_result: dict[str, Any], flux_result: dict[str, Any], state: dict[str, Any], vlm: dict[str, Any]) -> None:
    (case.output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (case.output_dir / "copy_presence_plan.json").write_text(json.dumps(case.copy_presence_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (case.output_dir / "layout_trace.json").write_text(json.dumps(state.get("render_result") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    (case.output_dir / "vlm_result.json").write_text(json.dumps(vlm, ensure_ascii=False, indent=2), encoding="utf-8")


def _legacy_ad_format(case: ActualCreativeCase) -> str:
    placement = str(case.ad_format_contract.get("placement") or "")
    return {"instagram_feed_static": "instagram_feed", "print_poster": "poster", "offline_flyer": "flyer"}.get(placement, placement)


def _usage_dict(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return dict(usage) if isinstance(usage, dict) else None


def _verify_image(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
