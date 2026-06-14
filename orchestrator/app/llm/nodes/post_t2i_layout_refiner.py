"""Refine TextLayoutSpec after actual image generation."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import read_model
from orchestrator.app.llm.copy_layout_fit import reduce_optional_copy, validate_copy_layout_fit
from orchestrator.app.llm.layout_candidates import generate_layout_candidates, score_layout_candidate
from orchestrator.app.schemas.text_layout import CopySpec, CopyVisualIntent, ImageLayoutAnalysis, LayoutRefinementResult, TextLayoutSpec, TextStyleSpec


def post_t2i_layout_refiner_node(state: dict[str, Any]) -> dict[str, Any]:
    attempts = int(state.get("layout_revision_attempts") or 0)
    copy_spec = read_model(state, "copy_spec", CopySpec)
    style_spec = read_model(state, "text_style_spec", TextStyleSpec)
    intent = CopyVisualIntent(**state["copy_visual_intent"]) if state.get("copy_visual_intent") else None
    if copy_spec.copy_mode == "no_copy" or not copy_spec.get_renderable():
        current = read_model(state, "text_layout_spec", TextLayoutSpec)
        fit = validate_copy_layout_fit(copy_spec, current)
        result = LayoutRefinementResult(
            selected_candidate_id=current.spec_id,
            selected_layout=current,
            candidates=[],
            action="render",
            retry_feedback=[],
            metadata={"source_node": "post_t2i_layout_refiner", "no_copy": True},
        )
        return {"layout_refinement_result": result.model_dump(), "layout_copy_fit_report": fit.model_dump(), "status": "background_validating"}
    analysis_data = state.get("image_layout_analysis")
    if not analysis_data:
        current = read_model(state, "text_layout_spec", TextLayoutSpec)
        fit = validate_copy_layout_fit(copy_spec, current)
        result = LayoutRefinementResult(selected_candidate_id=current.spec_id, selected_layout=current, candidates=[], action="render" if fit.overall_fit else "manual_review", retry_feedback=fit.warnings, metadata={"source_node": "post_t2i_layout_refiner", "analysis_missing": True})
        return {"layout_refinement_result": result.model_dump(), "layout_copy_fit_report": fit.model_dump(), "status": "background_validating"}
    analysis = ImageLayoutAnalysis(**analysis_data)
    candidates = generate_layout_candidates(intent, analysis, copy_spec, style_spec)
    scores = [score_layout_candidate(candidate, copy_spec, analysis, reference_hint=(intent.reference_layout_hint if intent else None)) for candidate in candidates]
    ranked = sorted(zip(candidates, scores), key=lambda item: (item[1].hard_rejected, -item[1].final_score))
    selected_layout = _first_valid_layout(ranked)
    fit = validate_copy_layout_fit(copy_spec, selected_layout or read_model(state, "text_layout_spec", TextLayoutSpec)) if (selected_layout or state.get("text_layout_spec")) else None
    action = "render"
    update: dict[str, Any] = {}
    retry_feedback: list[str] = []
    if selected_layout is None:
        action = "regenerate_background" if attempts < 1 else "manual_review"
        retry_feedback.append("no_valid_layout_candidate")
    elif fit and not fit.overall_fit and attempts < 1:
        reduced, removed = reduce_optional_copy(copy_spec)
        if removed:
            copy_spec = reduced
            candidates = generate_layout_candidates(intent, analysis, copy_spec, style_spec)
            scores = [score_layout_candidate(candidate, copy_spec, analysis, reference_hint=(intent.reference_layout_hint if intent else None)) for candidate in candidates]
            ranked = sorted(zip(candidates, scores), key=lambda item: (item[1].hard_rejected, -item[1].final_score))
            retry_feedback.extend(f"removed_optional_role:{role}" for role in removed)
            selected_layout = _first_valid_layout(ranked)
            if selected_layout is None:
                fit = None
                action = "regenerate_background"
                retry_feedback.append("no_valid_layout_after_copy_reduction")
            else:
                fit = validate_copy_layout_fit(copy_spec, selected_layout)
                if fit.overall_fit:
                    update["copy_spec"] = copy_spec.model_dump()
                    action = "reduce_information"
                else:
                    action = "rewrite_copy"
                    retry_feedback.extend(fit.warnings)
        else:
            action = "rewrite_copy"
            retry_feedback.extend(fit.warnings)
    elif fit and not fit.overall_fit:
        action = "manual_review"
        retry_feedback.extend(fit.warnings)
    result = LayoutRefinementResult(selected_candidate_id=selected_layout.spec_id if selected_layout else None, selected_layout=selected_layout, candidates=scores, action=action, retry_feedback=retry_feedback, metadata={"source_node": "post_t2i_layout_refiner", "candidate_count": len(scores), "revision_attempts": attempts})
    if selected_layout:
        update["text_layout_spec"] = selected_layout.model_dump()
    update.update(
        {
            "layout_candidate_scores": [score.model_dump() for score in scores],
            "layout_refinement_result": result.model_dump(),
            "layout_copy_fit_report": (fit.model_dump() if fit else None),
            "layout_revision_attempts": attempts + (1 if action in {"reduce_information", "rewrite_copy", "regenerate_background"} else 0),
            "status": "background_validating",
        }
    )
    return update


def _first_valid_layout(ranked: list[tuple[TextLayoutSpec, Any]]) -> TextLayoutSpec | None:
    for layout, score in ranked:
        if not score.hard_rejected:
            return layout
    return None
