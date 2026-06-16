import json
from pathlib import Path
from PIL import Image

from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node

def run_phase5_test():
    print("🚀 Starting Phase 5.1 Manual Subject Metadata Auto Placement Test...")
    
    # Define test images (must exist)
    test_cases = [
        {
            "id": "auto_place_01_bottom_subject",
            "image_path": "data/outputs/job_62d14c3711f64ac0aefbf88310e52f8d/gpt_image_2_0.png",
            "subject_position": "bottom", # Manual metadata
            "marketing_copy": {
                "title": "BRIGHT SKIN", # Fallback key for headline
                "body": "Luminous glow for every day.", # Fallback key for subcopy
                "description": "Available online and in stores.", # Fallback key for footer
            },
            "copy_spec": { # Also testing copy_spec parsing
                "items": [
                    {"role": "badge", "text": "NEW!"} # -> speech_bubble
                ]
            },
            "text_style_spec": {
                "typography": {
                    "primary_color": "#1E3A8A",
                    "secondary_color": "#4B5563"
                }
            }
        },
        {
            "id": "auto_place_02_right_subject",
            "image_path": "data/test_images/dark_product_shot.png",
            "subject_position": "right", # Manual metadata
            "marketing_copy": {
                "headline": "NOCTURNE",
                "subcopy": "Deep repair while you sleep.",
                "footer": "Dermatologist tested.",
            },
            "copy_spec": {},
            "text_style_spec": {
                "typography": {
                    "primary_color": "#FFFFFF",
                    "secondary_color": "#D1D5DB"
                }
            }
        },
        {
            "id": "auto_place_03_left_subject_fallback",
            "image_path": "data/test_images/dark_product_shot.png",
            "subject_position": "left", # Manual metadata -> Expect Fallback to center_stack
            "marketing_copy": {
                "headline": "FALLBACK TEST",
                "subcopy": "Should use center_stack.",
            },
            "copy_spec": {},
            "text_style_spec": {
                "typography": {
                    "primary_color": "#FFFFFF",
                    "secondary_color": "#D1D5DB"
                }
            }
        }
    ]
    
    report_data = []
    
    for tc in test_cases:
        sc_id = tc["id"]
        img_path = Path(tc["image_path"])
        
        print(f"\n▶ Testing Scenario: {sc_id} (Subject: {tc['subject_position']})")
        
        if not img_path.exists():
            print(f"  ❌ File not found: {img_path}")
            continue
            
        with Image.open(img_path) as img:
            canvas_w, canvas_h = img.size
            
        # Build initial state
        state = {
            "renderer_mode": "poster_components",
            "ad_format_spec": {"width": canvas_w, "height": canvas_h},
            "image_analysis": {
                "subject_position": tc["subject_position"],
                "source": "manual"
            },
            "marketing_copy": tc["marketing_copy"],
            "copy_spec": tc["copy_spec"],
            "text_style_spec": tc["text_style_spec"],
            "t2i_result": {"image_paths": [str(img_path)]},
            "job_id": f"test-phase5-{sc_id}"
        }
        
        # 1. Run Planner
        planner_result = poster_layout_planner_node(state)
        state.update(planner_result)
        
        layout_spec = state.get("poster_layout_spec")
        if not layout_spec:
            print("  ❌ Failed to generate poster_layout_spec")
            continue
            
        # 2. Run Renderer
        render_result_state = poster_renderer_node(state)
        
        render_result = render_result_state.get("render_result")
        if isinstance(render_result, str):
            render_result = json.loads(render_result)
        
        meta = render_result.get("metadata", {})
        quality_pass = meta.get("quality_pass", False)
        planner_diag = meta.get("planner_diagnostics", {})
        
        print(f"  ✅ RENDERED: {render_result.get('final_image_path')}")
        print(f"  ✅ Quality Pass: {quality_pass}")
        print(f"  🔍 Planner Selected Preset: {planner_diag.get('selected_preset')}")
        if planner_diag.get("fallback_used"):
            print(f"  ⚠️ Fallback Used: {planner_diag.get('fallback_reason')}")
        
        report_data.append({
            "scenario_id": sc_id,
            "subject_position": tc["subject_position"],
            "selected_preset": planner_diag.get("selected_preset"),
            "quality_pass": quality_pass,
            "fallback_used": planner_diag.get("fallback_used"),
            "final_image_path": render_result.get("final_image_path")
        })
        
    out_dir = Path("data/outputs/test-phase5-poc")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "auto_placement_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Phase 5.1 Testing Complete! Report saved to {report_path}")


if __name__ == "__main__":
    run_phase5_test()
