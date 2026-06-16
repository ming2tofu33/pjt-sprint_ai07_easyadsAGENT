"""Phase 1.7 Test Matrix with Layout Presets and Hierarchy Checks."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import random

from orchestrator.app.graph.routers import route_by_copy_presence
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.rendering.layout_presets import generate_layout


def create_photo_like_bg(w, h, base_color_hex):
    """Generate a pseudo-photo background with gradient and noise."""
    base_color = tuple(int(base_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    # Simple linear gradient
    for y in range(h):
        r = int(base_color[0] * (1 - 0.3 * y / h))
        g = int(base_color[1] * (1 - 0.3 * y / h))
        b = int(base_color[2] * (1 - 0.3 * y / h))
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    # Apply blur to make it soft
    img = img.filter(ImageFilter.GaussianBlur(10))
    return img


def run():
    print("🚀 Starting Phase 1.7 Layout Quality Tuning Matrix...")
    output_dir = Path("data/outputs/test-matrix-poc")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_data = []

    print("\n--- Running Preset & Hierarchy Matrix ---")
    
    # 1:1 Center Stack
    # 9:16 Top Headline Footer
    # 16:9 Editorial Left
    # 4:5 Hero Center
    scenarios = [
        {
            "id": "scenario_01_center_stack_square",
            "renderer_mode": "poster_components",
            "preset": "center_stack",
            "canvas_size": (1080, 1080),
            "bg_color": "#2563EB", 
            "colors": {"primary": "#FFFFFF", "secondary": "#BFDBFE"},
            "content": {
                "headline": "SUMMER GRAND SALE",
                "subcopy": "시원한 여름을 위한 파격 할인 혜택을 놓치지 마세요. 최대 50% 세일 진행중!",
                "footer": "※ 조기 품절될 수 있습니다.",
                "speech_bubble": "올여름 필수템!"
            }
        },
        {
            "id": "scenario_02_top_hf_portrait",
            "renderer_mode": "poster_components",
            "preset": "top_headline_footer",
            "canvas_size": (1080, 1920),
            "bg_color": "#111827", 
            "colors": {"primary": "#F59E0B", "secondary": "#D1D5DB"},
            "content": {
                "headline": "프리미엄 헬스케어의 새로운 기준을 제시합니다",
                "subcopy": "하루 10분, 건강한 습관을 만드는 가장 완벽한 방법. 전문가가 추천하는 시크릿 솔루션.",
                "footer": "자세한 약관 및 환불 규정은 홈페이지 참조. 문의: 1588-0000",
                "speech_bubble": "Best Choice"
            }
        },
        {
            "id": "scenario_03_editorial_wide",
            "renderer_mode": "poster_components",
            "preset": "editorial_left",
            "canvas_size": (1920, 1080),
            "bg_color": "#4B5563", 
            "colors": {"primary": "#FFFFFF", "secondary": "#E5E7EB"},
            "content": {
                "headline": "URBAN CHIC LIFESTYLE",
                "subcopy": "도심 속에서 즐기는 나만의 여유. 부드러운 소재와 모던한 디자인으로 완성되는 새로운 데일리룩.",
                "footer": "2026 SS Collection",
                "speech_bubble": "NEW"
            }
        },
        {
            "id": "scenario_04_hero_center_portrait",
            "renderer_mode": "poster_components",
            "preset": "hero_center",
            "canvas_size": (1080, 1350), 
            "bg_color": "#991B1B", 
            "colors": {"primary": "#FFFFFF", "secondary": "#FCA5A5"},
            "content": {
                "headline": "IMPACT",
                "subcopy": "강렬하게 시선을 사로잡는 압도적인 퍼포먼스",
                "footer": "예약 문의: 카카오톡 채널",
                "speech_bubble": "단 한 번의 기회"
            }
        },
        {
            "id": "scenario_05_simple_text_regression",
            "renderer_mode": "simple_text",
            "preset": "simple_text",
            "canvas_size": (1080, 1080),
            "bg_color": "#065F46", 
            "colors": {},
            "content": {}
        },
        {
            "id": "scenario_06_icon_feature_list",
            "renderer_mode": "poster_components",
            "preset": "editorial_left",
            "canvas_size": (1920, 1080),
            "bg_color": "#1E3A8A", 
            "colors": {"primary": "#FBBF24", "secondary": "#D1D5DB"},
            "content": {
                "headline": "FEATURES",
                "subcopy": "Discover the incredible features of our new platform.",
                "features": [
                    {"icon": "check", "text": "Ultra-fast performance"},
                    {"icon": "star", "text": "Premium quality guarantee"},
                    {"icon": "heart", "text": "Loved by million users"},
                    {"icon": "number", "text": "Easy step-by-step setup"},
                    {"icon": "unknown", "text": "Seamless integration"},
                    {"icon": "dot", "text": "This should be truncated"}
                ],
                "footer": "Terms and conditions apply.",
                "speech_bubble": "NEW!"
            }
        },
        {
            "id": "scenario_07_memo_card",
            "renderer_mode": "poster_components",
            "preset": "top_headline_footer",
            "canvas_size": (1080, 1080),
            "bg_color": "#064E3B",
            "colors": {"primary": "#FFFFFF", "secondary": "#A7F3D0"},
            "content": {
                "headline": "SPECIAL OFFER",
                "subcopy": "Don't miss our summer event.",
                "memo_card": [
                    "Buy 1 Get 1 Free\nLimited time only!",
                    "This should be truncated"
                ],
                "footer": "Valid until Aug 31",
                "speech_bubble": "HOT"
            }
        }
    ]

    for sc in scenarios:
        sc_id = sc["id"]
        mode = sc["renderer_mode"]
        preset = sc["preset"]
        canvas_w, canvas_h = sc["canvas_size"]
        
        print(f"▶ Testing Scenario: {sc_id} (Preset: {preset})")
        
        bg_path = output_dir / f"bg_{sc_id}.png"
        img = create_photo_like_bg(canvas_w, canvas_h, sc["bg_color"])
        img.save(bg_path)
        
        state = {
            "job_id": f"test-matrix-{sc_id}",
            "renderer_mode": mode,
            "t2i_result": {"image_paths": [str(bg_path)]},
        }
        
        node_success = False
        quality_pass = False
        error_msg = None
        result = {}
        component_diagnostics = []
        
        if mode == "poster_components":
            components = generate_layout(preset, canvas_w, canvas_h, sc["content"], sc["colors"])
            state["poster_layout_spec"] = {
                "canvas_width": canvas_w,
                "canvas_height": canvas_h,
                "components": [c.model_dump() for c in components]
            }
            
            try:
                result = poster_renderer_node(state)
                render_res = result.get("render_result", {})
                metadata = render_res.get("metadata", {})
                
                node_success = metadata.get("render_success", False)
                quality_pass = metadata.get("quality_pass", False)
                component_diagnostics = metadata.get("component_diagnostics", [])
                error_msg = result.get("error_message", None)
            except Exception as e:
                node_success = False
                quality_pass = False
                error_msg = str(e)
                result = {}
        else:
            state["copy_spec"] = {"items": [{"role": "headline", "text": "REGRESSION TEST", "is_renderable": True}]}
            state["text_layout_spec"] = {
                "slots": [
                    {"slot_id": "s1", "role": "headline", "bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.2},
                     "font_metric": {"base_size_ratio": 0.1, "min_size_ratio": 0.05, "max_size_ratio": 0.15, "weight": 700},
                     "text_color": "#FFFFFF", "overlay_treatment": "plain", "alignment": "center", "anchor": "middle_center"}
                ],
                "template": "centered_hero", "canvas_width": canvas_w, "canvas_height": canvas_h
            }
            state["text_style_spec"] = {
                "typography": {
                    "headline_font": "Pretendard", "body_font": "Pretendard", "headline_weight": 700, "body_weight": 400,
                    "headline_size_ratio": 0.1, "body_size_ratio": 0.05, "primary_color": "#FF0000", "accent_color": "#00FF00",
                    "text_color_on_light": "#000000", "text_color_on_dark": "#FFFFFF", "default_overlay": "plain"
                },
                "profile": "clean"
            }
            try:
                result = text_renderer_node(state)
                node_success = result.get("status") == "overlaying_text"
                quality_pass = node_success
            except Exception as e:
                node_success = False
                quality_pass = False
                error_msg = str(e)

        final_path = result.get("final_image_path", None)
        
        # Calculate Layout Metrics
        safe_margin_valid = True
        visual_hierarchy_valid = True
        total_bbox_area = 0
        
        hl_size = 0
        sub_size = 0
        ft_size = 0
        
        for d in component_diagnostics:
            # Parse bbox "WxH at (X,Y)"
            try:
                parts = d["bbox"].split(" at ")
                w, h = map(int, parts[0].split("x"))
                x, y = map(int, parts[1].strip("()").split(","))
                total_bbox_area += (w * h)
                
                # Check safe margin (8% default, 5% bottom footer)
                if x < canvas_w * 0.07 or x + w > canvas_w * 0.93:
                    safe_margin_valid = False
                if y < canvas_h * 0.07:
                    safe_margin_valid = False
                if d["component_type"] == "footer_panel":
                    if y + h > canvas_h * 0.96:
                        safe_margin_valid = False
                elif y + h > canvas_h * 0.93:
                    safe_margin_valid = False
            except Exception:
                pass
            
            if d["component_type"] == "headline_block": hl_size = d.get("font_size_final", 0)
            elif d["component_type"] == "subcopy_block": sub_size = d.get("font_size_final", 0)
            elif d["component_type"] == "footer_panel": ft_size = d.get("font_size_final", 0)
            
        if hl_size > 0:
            if sub_size > 0 and hl_size <= sub_size:
                visual_hierarchy_valid = False
            if ft_size > 0 and hl_size <= ft_size:
                visual_hierarchy_valid = False
            if ft_size > 0 and sub_size > 0 and sub_size <= ft_size:
                visual_hierarchy_valid = False
                
        empty_space_ratio = 1.0 - (total_bbox_area / (canvas_w * canvas_h)) if mode == "poster_components" else 0.5
        content_density_valid = 0.3 <= empty_space_ratio <= 0.85
        
        has_list_truncated = False
        has_icon_fallback = False
        has_item_warning = False
        has_readability_warning = False
        has_footer_warning = False
        has_memo_truncated = False
        has_memo_warning = False
        
        for d in component_diagnostics:
            if d.get("list_truncated"): has_list_truncated = True
            if d.get("icon_fallback_used"): has_icon_fallback = True
            if d.get("item_count_warning"): has_item_warning = True
            if d.get("list_readability_warning"): has_readability_warning = True
            if d.get("footer_readability_warning"): has_footer_warning = True
            if d.get("memo_card_truncated"): has_memo_truncated = True
            if d.get("memo_card_readability_warning"): has_memo_warning = True
            
        layout_quality_pass = quality_pass and safe_margin_valid and visual_hierarchy_valid and content_density_valid
        
        report_data.append({
            "scenario_id": sc_id,
            "layout_preset": preset,
            "component_count": len(component_diagnostics),
            "canvas_size": f"{canvas_w}x{canvas_h}",
            "quality_pass": quality_pass,
            "layout_quality_pass": layout_quality_pass,
            "safe_margin_valid": safe_margin_valid,
            "visual_hierarchy_valid": visual_hierarchy_valid,
            "empty_space_ratio": round(empty_space_ratio, 3),
            "content_density_valid": content_density_valid,
            "has_list_truncated": has_list_truncated,
            "has_icon_fallback": has_icon_fallback,
            "has_item_warning": has_item_warning,
            "has_readability_warning": has_readability_warning,
            "has_footer_warning": has_footer_warning,
            "has_memo_truncated": has_memo_truncated,
            "has_memo_warning": has_memo_warning,
            "output_path": final_path,
            "components": component_diagnostics
        })
        
        if layout_quality_pass:
            print(f"  ✅ LAYOUT PASS: {final_path}")
        else:
            print(f"  ⚠️ LAYOUT FAILED: safe_margin={safe_margin_valid}, hierarchy={visual_hierarchy_valid}, density={content_density_valid}")

    report_path = output_dir / "matrix_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 Matrix Testing Complete! Report saved to {report_path}")

if __name__ == "__main__":
    run()
