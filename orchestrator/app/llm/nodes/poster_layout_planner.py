"""Phase 5.1 Manual Subject Metadata Auto Placement Planner."""

import logging
from typing import Any

from orchestrator.app.rendering.layout_presets import generate_layout
from orchestrator.app.schemas.text_layout import CopySpec

logger = logging.getLogger(__name__)


def poster_layout_planner_node(state: dict) -> dict[str, object]:
    """
    Reads image metadata (subject_position) and copy content,
    and automatically calculates the appropriate layout preset and component bounding boxes.
    """
    # 1. 덮어쓰기 방지 (이미 존재하는 경우 보존)
    if state.get("poster_layout_spec"):
        logger.info("[PosterLayoutPlanner] Existing poster_layout_spec found. Preserving layout.")
        # Diagnostics에 보존 내역만 남기고 그대로 통과
        render_result = state.get("render_result", {})
        if isinstance(render_result, dict):
            meta = render_result.get("metadata", {})
            meta["planner_diagnostics"] = {
                "planner_used": True,
                "planner_source": "poster_layout_planner_node",
                "existing_layout_preserved": True,
                "auto_layout_enabled": False,
                "bbox_adjustment_skipped": True,
                "bbox_adjustment_reason": "existing poster_layout_spec preserved"
            }
            render_result["metadata"] = meta
            return {"render_result": render_result}
        return {}

    # 2. 이미지 사이즈 획득 (가장 최근 결과 우선)
    w, h = 1024, 1024
    if state.get("t2i_result"):
        t2i_result = state["t2i_result"]
        if isinstance(t2i_result, dict) and "image_paths" in t2i_result and t2i_result["image_paths"]:
            # Load dimensions if possible (for now rely on ad_format_spec or defaults)
            pass
    ad_format_spec = state.get("ad_format_spec", {})
    if isinstance(ad_format_spec, dict):
        w = int(ad_format_spec.get("width") or 1024)
        h = int(ad_format_spec.get("height") or 1024)

    # 3. Manual Subject Metadata 획득 및 Preset 맵핑 (Fallback 처리)
    image_analysis = state.get("image_analysis") or {}
    subject_position = image_analysis.get("subject_position", "center")
    safe_zone = image_analysis.get("safe_zone", "unknown")
    background_complexity = image_analysis.get("background_complexity", "unknown")
    confidence = image_analysis.get("confidence", 1.0)
    
    preset_name = "center_stack"
    fallback_used = False
    fallback_reason = ""
    policy_reason = ""
    planning_warnings = []

    # Policy Engine (Phase 5.3) - we pass this context to registry
    planner_policy_context = {
        "confidence": confidence,
        "background_complexity": background_complexity,
        "subject_position": subject_position,
        "safe_zone": safe_zone
    }
    
    # 3.5 Use Template Registry (Phase 6)
    from orchestrator.app.rendering.template_registry import select_template
    
    requested_template_id = state.get("requested_template_id")
    
    # We don't have components_to_render built yet, but we will pass aspect ratio
    # Aspect ratio logic
    aspect_ratio = "unknown"
    if w == h:
        aspect_ratio = "1:1"
    elif w < h:
        if abs(w/h - 4/5) < 0.1:
            aspect_ratio = "4:5"
        elif abs(w/h - 9/16) < 0.1:
            aspect_ratio = "9:16"
            
    # For unsupported check, we can gather components from copy_spec
    # Just a light check for Phase 6 before full component parsing
    components_to_render = []
    copy_spec_data = state.get("copy_spec")
    if copy_spec_data:
        if isinstance(copy_spec_data, dict):
            items = copy_spec_data.get("items", [])
        else:
            items = getattr(copy_spec_data, "items", [])
        for item in items:
            role = item.get("role")
            if role in ["headline"]:
                components_to_render.append({"type": "headline_block"})
            elif role in ["subheadline", "body"]:
                components_to_render.append({"type": "subcopy_block"})
            elif role in ["cta", "store_info", "disclaimer"]:
                components_to_render.append({"type": "footer_panel"})
            elif role in ["badge", "promotion"]:
                components_to_render.append({"type": "speech_bubble"})

    template_def, template_diagnostics = select_template(
        image_analysis=image_analysis,
        planner_policy=planner_policy_context,
        requested_template_id=requested_template_id,
        components_to_render=components_to_render,
        aspect_ratio=aspect_ratio
    )
    
    preset_name = template_def.preset_name if template_def else "center_stack"
    
    fallback_used = False
    fallback_reason = ""
    policy_reason = template_diagnostics.get("template_policy_reason", "")
    planning_warnings = []
    
    if template_diagnostics.get("template_fallback_used"):
        fallback_used = True
        fallback_reason = template_diagnostics.get("template_fallback_reason", "")
    elif confidence < 0.5:
        fallback_used = True
        fallback_reason = "confidence below threshold"
        planning_warnings.append("Confidence below threshold. BBox adjustment might be skipped.")
    elif background_complexity == "high":
        fallback_used = True
        fallback_reason = "high background complexity"
        planning_warnings.append("Background complexity is high. Text placement might be risky. Contrast warning may apply.")

    # 4. Copy 파싱 및 Fallback 로직 (content 딕셔너리 구축)
    content = {}
    
    # MarketingCopy에서 가져오기
    marketing_copy = state.get("marketing_copy", {})
    if not isinstance(marketing_copy, dict):
        marketing_copy = getattr(marketing_copy, "model_dump", lambda: {})() or {}

    # CopySpec에서 가져오기
    copy_spec_data = state.get("copy_spec", {})
    if not isinstance(copy_spec_data, dict):
        copy_spec_data = getattr(copy_spec_data, "model_dump", lambda: {})() or {}

    items = copy_spec_data.get("items", [])
    for item in items:
        role = item.get("role")
        text = item.get("text")
        if not text:
            continue
        if role == "headline":
            content["headline"] = text
        elif role == "subheadline" or role == "body":
            content["subcopy"] = text
        elif role == "cta" or role == "store_info" or role == "disclaimer":
            content["footer"] = text
        elif role == "badge" or role == "promotion":
            content["speech_bubble"] = text

    # 추가 Fallback: marketing_copy나 current_brief에서 흔한 키워드 긁어오기
    if "headline" not in content:
        content["headline"] = marketing_copy.get("headline") or marketing_copy.get("title") or state.get("user_custom_headline")
        if not content["headline"]:
            planning_warnings.append("No headline found in copy_spec or fallback sources.")
            content["headline"] = "HEADLINE" # 최소 렌더링 보장

    if "subcopy" not in content:
        content["subcopy"] = marketing_copy.get("subheadline") or marketing_copy.get("subcopy") or marketing_copy.get("main_copy") or marketing_copy.get("body") or state.get("user_custom_subcopy")

    if "footer" not in content:
        content["footer"] = marketing_copy.get("footer") or marketing_copy.get("description")

    # None 필터링
    content = {k: v for k, v in content.items() if v}

    # 5. 스타일/색상 추출
    colors = {"primary": "#FFFFFF", "secondary": "#E0E0E0"}
    text_style_spec = state.get("text_style_spec", {})
    if text_style_spec:
        if isinstance(text_style_spec, dict):
            typography = text_style_spec.get("typography", {})
            if typography.get("primary_color"):
                colors["primary"] = typography["primary_color"]
            if typography.get("secondary_color"):
                colors["secondary"] = typography["secondary_color"]
        else:
            typography = getattr(text_style_spec, "typography", None)
            if typography:
                if getattr(typography, "primary_color", None):
                    colors["primary"] = typography.primary_color
                if getattr(typography, "secondary_color", None):
                    colors["secondary"] = typography.secondary_color

    # 6. Layout Preset 실행
    try:
        components = generate_layout(preset_name, w, h, content, colors)
    except Exception as e:
        logger.error(f"Failed to generate layout using preset {preset_name}: {e}")
        components = []
        planning_warnings.append(f"Layout generation failed: {e}")

    # Phase 5.4: BBox Adjustment Engine
    image_aware_bbox_adjustment_applied = False
    bbox_adjustment_source = "poster_layout_planner_node"
    bbox_adjustment_fallback = False
    bbox_adjustment_skipped = False
    bbox_adjustment_reason = ""
    bbox_clamped = False
    component_overlap_prevented = False
    safe_margin_applied = False
    
    MIN_WIDTH = 0.1
    MIN_HEIGHT = 0.05
    MARGIN = 0.05
    
    adjusted_components = []
    
    if confidence < 0.5:
        bbox_adjustment_fallback = True
        bbox_adjustment_reason = "confidence below threshold, adjustment skipped"
        for c in components:
            c_dict = c.model_dump() if hasattr(c, "model_dump") else c
            adjusted_components.append(c_dict)
    else:
        image_aware_bbox_adjustment_applied = True
        bbox_adjustment_reason = "adjusted based on safe_zone and subject_position"
        
        last_y_bottom = 0.0
        
        for c in components:
            c_dict = c.model_dump() if hasattr(c, "model_dump") else c
            role = c_dict.get("type", "").replace("_block", "").replace("_panel", "")
            # e.g., 'headline_block' -> 'headline', 'footer_panel' -> 'footer'
            
            bbox = c_dict.get("bbox", {})
            bx, by = bbox.get("x", 0.0), bbox.get("y", 0.0)
            bw, bh = bbox.get("w", 1.0), bbox.get("h", 1.0)
            
            orig_bx, orig_by, orig_bw, orig_bh = bx, by, bw, bh
            
            if role in ["headline", "subcopy", "body"]:
                if safe_zone == "left":
                    bx = MARGIN
                    safe_margin_applied = True
                if safe_zone == "top" and role == "headline":
                    by = MARGIN
                    safe_margin_applied = True
                
                if subject_position == "right":
                    max_w = 0.5 - bx
                    if bw > max_w:
                        bw = max_w
                        
            elif role == "footer" and subject_position == "bottom":
                planning_warnings.append("Footer component might overlap with subject at bottom.")
                
            if background_complexity == "high" and role in ["headline", "subcopy", "body"]:
                bw = min(bw, 0.6)
                
            # Clamp
            if bx < 0.0: bx, bbox_clamped = 0.0, True
            if by < 0.0: by, bbox_clamped = 0.0, True
            if bx + bw > 1.0: bw, bbox_clamped = 1.0 - bx, True
            if by + bh > 1.0: bh, bbox_clamped = 1.0 - by, True
            
            # Overlap Prevention (단순 Y축 보정)
            if role in ["subcopy", "body"] and by < last_y_bottom:
                by = last_y_bottom + 0.02
                component_overlap_prevented = True
                if by + bh > 1.0:
                    bh = 1.0 - by
                    bbox_clamped = True
            
            if role in ["headline", "subcopy", "body"]:
                last_y_bottom = by + bh
                
            # Minimum Size Fallback
            if bw < MIN_WIDTH or bh < MIN_HEIGHT:
                bx, by, bw, bh = orig_bx, orig_by, orig_bw, orig_bh
                bbox_adjustment_fallback = True
                bbox_adjustment_reason += f" | {role} bbox too small, reverted"
                
            bbox.update({"x": bx, "y": by, "w": bw, "h": bh})
            c_dict["bbox"] = bbox
            c_dict["diagnostics"] = {
                "original_bbox": {"x": orig_bx, "y": orig_by, "w": orig_bw, "h": orig_bh},
                "adjusted_bbox": bbox,
                "bbox_clamped": bbox_clamped,
                "safe_margin_applied": safe_margin_applied
            }
            adjusted_components.append(c_dict)

    poster_layout_spec = {
        "canvas_width": w,
        "canvas_height": h,
        "components": adjusted_components
    }

    # 7. Diagnostics 기록
    diagnostics = {
        "planner_used": True,
        "planner_source": "poster_layout_planner_node",
        "subject_position": subject_position,
        "safe_zone": safe_zone,
        "background_complexity": background_complexity,
        "confidence": confidence,
        "selected_preset": preset_name,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "policy_reason": policy_reason,
        "image_aware_policy_applied": True,
        "image_aware_bbox_adjustment_applied": image_aware_bbox_adjustment_applied,
        "bbox_adjustment_source": bbox_adjustment_source,
        "bbox_adjustment_fallback": bbox_adjustment_fallback,
        "bbox_adjustment_skipped": bbox_adjustment_skipped,
        "bbox_adjustment_reason": bbox_adjustment_reason,
        "bbox_clamped": bbox_clamped,
        "component_overlap_prevented": component_overlap_prevented,
        "safe_margin_applied": safe_margin_applied,
        "auto_layout_enabled": True,
        "existing_layout_preserved": False,
        "planning_warnings": planning_warnings
    }

    # 반환 객체 구성
    render_result = state.get("render_result", {})
    if not isinstance(render_result, dict):
        render_result = getattr(render_result, "model_dump", lambda: {})() or {}
    
    meta = render_result.get("metadata", {})
    meta["planner_diagnostics"] = diagnostics
    meta["template_diagnostics"] = template_diagnostics
    render_result["metadata"] = meta

    return {
        "poster_layout_spec": poster_layout_spec,
        "render_result": render_result
    }
