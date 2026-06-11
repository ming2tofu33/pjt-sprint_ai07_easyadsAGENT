import logging
from typing import Any

logger = logging.getLogger(__name__)

SAFE_ZONE_CENTER_THRESHOLD = 0.6
RIGHT_SUBJECT_REGION_START = 0.75
BOTTOM_SUBJECT_REGION_START = 0.85
LOW_CONFIDENCE_THRESHOLD = 0.5

def image_aware_quality_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Validates if the finalized placement is safe given the image analysis.
    This does NOT mutate the placement or components. It only outputs diagnostics.
    """
    render_result = state.get("render_result", {})
    if not isinstance(render_result, dict):
        render_result = render_result.model_dump() if hasattr(render_result, "model_dump") else {}
        
    meta = render_result.get("metadata", {})
    
    # 1. Gather inputs
    image_analysis = state.get("image_analysis", {})
    if not image_analysis:
        image_analysis = meta.get("image_analysis_diagnostics", {})
        
    safe_zone = image_analysis.get("safe_zone", "unknown")
    subject_position = image_analysis.get("subject_position", "unknown")
    background_complexity = image_analysis.get("background_complexity", "low")
    confidence = image_analysis.get("confidence", 1.0)
    
    planner_diagnostics = meta.get("planner_diagnostics", {})
    bbox_adj_applied = planner_diagnostics.get("image_aware_bbox_adjustment_applied", False)
    
    # Raw components from state (contains the final BBoxes output by planner before or during rendering)
    poster_layout_spec = state.get("poster_layout_spec", {})
    components = poster_layout_spec.get("components", [])
    
    # Initialize output fields
    image_aware_quality_gate_applied = True
    image_aware_quality_pass = True
    image_aware_quality_warning = False
    safe_zone_alignment_valid = True
    subject_overlap_risk = False
    confidence_policy_valid = True
    background_complexity_warning = False
    warnings = []
    
    # Analyze main texts
    main_texts = []
    footers = []
    
    for c in components:
        role = c.get("type", "").replace("_block", "").replace("_panel", "")
        if role in ["headline", "subcopy"]:
            main_texts.append(c)
        elif role == "footer":
            footers.append(c)
            
    # Safe Zone Alignment Check
    for c in main_texts:
        bbox = c.get("bbox", {})
        bx = bbox.get("x", 0.0)
        by = bbox.get("y", 0.0)
        bw = bbox.get("w", 1.0)
        bh = bbox.get("h", 1.0)
        
        cx = bx + bw / 2.0
        cy = by + bh / 2.0
        
        if safe_zone == "left" and cx > SAFE_ZONE_CENTER_THRESHOLD:
            safe_zone_alignment_valid = False
            image_aware_quality_warning = True
            warnings.append(f"safe_zone=left but {c.get('type')} bbox is not located in left area")
            
        if safe_zone == "top" and cy > SAFE_ZONE_CENTER_THRESHOLD:
            safe_zone_alignment_valid = False
            image_aware_quality_warning = True
            warnings.append(f"safe_zone=top but {c.get('type')} bbox is not located in top area")
            
    if safe_zone == "unknown":
        image_aware_quality_warning = True
        warnings.append("safe_zone=unknown, conservative warning recorded")

    # Subject Overlap Risk Check
    for c in main_texts:
        bbox = c.get("bbox", {})
        bx = bbox.get("x", 0.0)
        bw = bbox.get("w", 1.0)
        if subject_position == "right" and bx + bw > RIGHT_SUBJECT_REGION_START:
            subject_overlap_risk = True
            warnings.append(f"subject_position=right and {c.get('type')} bbox crosses into right subject region")
            
    for c in footers:
        bbox = c.get("bbox", {})
        by = bbox.get("y", 0.0)
        bh = bbox.get("h", 1.0)
        if subject_position == "bottom" and by + bh > BOTTOM_SUBJECT_REGION_START:
            subject_overlap_risk = True
            warnings.append(f"subject_position=bottom and footer remains near bottom area")

    # Confidence Policy Check
    if confidence < LOW_CONFIDENCE_THRESHOLD and bbox_adj_applied:
        confidence_policy_valid = False
        warnings.append("confidence below threshold but bbox adjustment was applied")
        
    # Background Complexity Check
    if background_complexity == "high":
        background_complexity_warning = True
        warnings.append("background_complexity=high, readability review recommended")
        
    # Map physical render errors to logical gate pass
    quality_pass = meta.get("quality_pass", True)
    if not quality_pass:
        # We don't fail `image_aware_quality_pass` solely on `quality_pass` because they measure different things,
        # but we can record it as a warning in the placement validation.
        warnings.append("physical render constraints failed (e.g. clipping or overflow)")
        
    # Evaluate final pass/fail for image-aware quality
    if not safe_zone_alignment_valid or subject_overlap_risk or not confidence_policy_valid:
        image_aware_quality_pass = False

    reason = "All logical placements match image constraints."
    if not image_aware_quality_pass:
        reason = "Validation failed: " + "; ".join(warnings[:2])
    elif image_aware_quality_warning or warnings:
        reason = "Validation passed with warnings: " + "; ".join(warnings[:2])

    diag = {
        "image_aware_quality_gate_applied": image_aware_quality_gate_applied,
        "image_aware_quality_pass": image_aware_quality_pass,
        "image_aware_quality_warning": image_aware_quality_warning or len(warnings) > 0,
        "image_aware_quality_reason": reason,
        "safe_zone_alignment_valid": safe_zone_alignment_valid,
        "subject_overlap_risk": subject_overlap_risk,
        "confidence_policy_valid": confidence_policy_valid,
        "background_complexity_warning": background_complexity_warning,
        "placement_validation_warnings": warnings
    }
    
    meta["image_aware_quality_diagnostics"] = diag
    
    if "render_result" not in state:
        state["render_result"] = {}
        
    # Make sure we don't mutate a Pydantic object directly without recreation
    if hasattr(state["render_result"], "model_dump"):
        # For simplicity, we assume state is dealing with dicts
        # (Poster_renderer_node returned a dict via model_dump())
        state["render_result"] = state["render_result"].model_dump()
        
    if isinstance(state.get("render_result"), dict):
        state["render_result"]["metadata"] = meta
    
    return state
