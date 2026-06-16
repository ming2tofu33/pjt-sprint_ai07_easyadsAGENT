import logging

logger = logging.getLogger(__name__)

def generate_rule_based_reason(image_analysis: dict, template_diag: dict, quality_warnings: list, minor_warnings: list) -> tuple[str, str]:
    en_parts = []
    ko_parts = []
    
    # 1. Base selection reason
    sp = image_analysis.get("subject_position")
    sz = image_analysis.get("safe_zone")
    preset = template_diag.get("selected_preset_name")
    
    if sp and sz and preset:
        en_parts.append(f"Subject is positioned on the {sp} and the safe zone is on the {sz}, so the {preset} layout was selected.")
        
        ko_preset_desc = "중앙 정렬"
        if preset == "editorial_left": ko_preset_desc = "좌측 정렬"
        elif preset == "editorial_right": ko_preset_desc = "우측 정렬"
        elif preset == "top_headline_footer": ko_preset_desc = "상하단 분리"
        elif preset == "hero_center": ko_preset_desc = "타이포그래피 중심"
        
        pos_ko = {"left": "왼쪽", "right": "오른쪽", "top": "상단", "bottom": "하단", "center": "중앙"}
        sp_ko = pos_ko.get(sp, sp)
        sz_ko = pos_ko.get(sz, sz)
            
        ko_parts.append(f"피사체가 {sp_ko}에 있고 안전 영역이 {sz_ko}에 있어 {ko_preset_desc} 템플릿을 선택했습니다.")
    else:
        en_parts.append("Default or fallback template was selected due to missing image analysis context.")
        ko_parts.append("이미지 분석 정보 부족으로 기본 또는 폴백 템플릿이 선택되었습니다.")
        
    # 2. Critical/Quality warnings
    if quality_warnings:
        en_parts.append("Critical issues detected: " + ", ".join(quality_warnings) + ".")
        ko_parts.append("다음 심각한 문제가 발견되었습니다: " + ", ".join(quality_warnings) + ".")
        
    # 3. Minor warnings
    if minor_warnings and not quality_warnings:
        en_parts.append("Minor issues to review: " + ", ".join(minor_warnings) + ".")
        ko_parts.append("가벼운 검토가 필요한 항목이 있습니다: " + ", ".join(minor_warnings) + ".")
        
    return " ".join(en_parts), " ".join(ko_parts)

def design_recommendation_node(state: dict) -> dict:
    """
    Aggegates all diagnostics and provides a final recommendation level and reason.
    Does NOT modify the actual rendering outcome.
    """
    render_result = state.get("render_result", {})
    if not isinstance(render_result, dict):
        render_result_dict = getattr(render_result, "model_dump", lambda: {})() or {}
        if not render_result_dict:
            # Maybe it's a raw object
            render_result_dict = {"metadata": getattr(render_result, "metadata", {})}
    else:
        render_result_dict = render_result
        
    meta = render_result_dict.get("metadata", {})
    
    image_analysis = state.get("image_analysis", {})
    template_diag = meta.get("template_diagnostics", {})
    asset_diag = meta.get("asset_diagnostics", {})
    ia_quality_diag = meta.get("image_aware_quality_diagnostics", {})
    component_diag = meta.get("component_diagnostics", [])
    
    # Base indicators
    render_success = meta.get("render_success", False)
    quality_pass = meta.get("quality_pass", False)
    
    # Image aware quality indicators
    ia_quality_pass = ia_quality_diag.get("image_aware_quality_pass", True)
    safe_zone_valid = ia_quality_diag.get("safe_zone_alignment_valid", True)
    overlap_risk = ia_quality_diag.get("subject_overlap_risk", False)
    confidence_valid = ia_quality_diag.get("confidence_policy_valid", True)
    
    # Gather warnings
    quality_warnings = []
    minor_warnings = []
    
    # Critical Warnings Check
    final_overflow = False
    clipped_by_canvas = False
    component_error = False
    decorative_overlap = False
    contrast_warning = False
    
    for cd in component_diag:
        if cd.get("final_overflow_detected"): final_overflow = True
        if cd.get("clipped_by_canvas"): clipped_by_canvas = True
        if cd.get("component_error"): component_error = True
        if cd.get("decorative_overlap_text"): decorative_overlap = True
        if cd.get("contrast_warning"): contrast_warning = True
        
    if final_overflow: quality_warnings.append("Text overflow detected")
    if clipped_by_canvas: quality_warnings.append("Component clipped by canvas")
    if component_error: quality_warnings.append("Component rendering error")
    if overlap_risk: quality_warnings.append("Subject overlap risk")
    if not safe_zone_valid: quality_warnings.append("Safe zone alignment invalid")
    
    # Minor Warnings Check
    bg_complexity = image_analysis.get("background_complexity", "low")
    if bg_complexity == "high": minor_warnings.append("High background complexity")
    if contrast_warning: minor_warnings.append("Contrast ratio warning")
    if decorative_overlap: minor_warnings.append("Decorative sticker overlapping text")
    if template_diag.get("template_fallback_used"): minor_warnings.append("Template fallback used")
    if asset_diag.get("asset_fallback_used"): minor_warnings.append("Asset fallback used")
    
    # Determine Recommendation Level
    level = "use_as_is"
    fallback_recommendation = None
    
    # Level 4: manual_review_required
    if not render_success or not quality_pass or final_overflow or clipped_by_canvas or component_error:
        level = "manual_review_required"
        fallback_recommendation = {
            "suggested_action": "manual_review",
            "reason": "Critical physical rendering failures or overflow detected."
        }
    # Level 3: retry_recommended
    elif not ia_quality_pass or not safe_zone_valid or overlap_risk or not confidence_valid:
        level = "retry_recommended"
        fallback_recommendation = {
            "suggested_action": "retry_with_fallback_template",
            "suggested_template_id": "center_stack_basic",
            "reason": "Image-aware policies failed. A more conservative layout is recommended."
        }
    # Level 2: minor_review
    elif minor_warnings:
        level = "minor_review"
        
    # Generate Reason
    reason_en, reason_ko = generate_rule_based_reason(image_analysis, template_diag, quality_warnings, minor_warnings)
    
    all_warnings = quality_warnings + minor_warnings
    
    design_recommendation = {
        "design_recommendation_applied": True,
        "recommendation_level": level,
        "recommended_template_id": template_diag.get("selected_template_id"),
        "recommended_preset_name": template_diag.get("selected_preset_name"),
        "recommended_assets": [], # Simplification, could aggregate all selected_asset_id
        "design_reason": reason_en,
        "design_reason_ko": reason_ko,
        "quality_summary": {
            "render_quality_pass": render_success and quality_pass,
            "layout_quality_pass": not final_overflow and not clipped_by_canvas,
            "image_aware_quality_pass": ia_quality_pass
        },
        "warnings": all_warnings,
        "fallback_recommendation": fallback_recommendation
    }
    
    # Update Metadata
    if isinstance(render_result, dict):
        if "metadata" not in render_result:
            render_result["metadata"] = {}
        render_result["metadata"]["design_recommendation"] = design_recommendation
    else:
        # If it's an object, we assume metadata is a mutable dict
        if hasattr(render_result, "metadata"):
            render_result.metadata["design_recommendation"] = design_recommendation
            
    return {"render_result": render_result}
