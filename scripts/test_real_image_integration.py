import json
from pathlib import Path
from PIL import Image

from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.rendering.layout_presets import LAYOUT_PRESETS

def run_integration_test():
    print("🚀 Starting Phase 2.3 Real Image Background Integration Test...")
    
    # Define test images (must exist)
    test_cases = [
        {
            "id": "real_img_01_gpt2",
            "image_path": "data/outputs/job_62d14c3711f64ac0aefbf88310e52f8d/gpt_image_2_0.png",
            "subject_position": "bottom", # Manual metadata
            "preset": "top_headline_footer", # Corresponding preset
            "content": {
                "headline": "BRIGHT SKIN",
                "subcopy": "Luminous glow for every day.",
                "memo_card": ["Best Seller\nSave 20% today!"],
                "footer": "Available online and in stores.",
                "speech_bubble": "NEW!"
            },
            "colors": {"primary": "#1E3A8A", "secondary": "#4B5563"} # Dark text for bright background
        },
        {
            "id": "real_img_02_dark_product",
            "image_path": "data/test_images/dark_product_shot.png",
            "subject_position": "right", # Manual metadata
            "preset": "editorial_left", # Corresponding preset
            "content": {
                "headline": "NOCTURNE",
                "subcopy": "Deep repair while you sleep.",
                "features": [
                    {"icon": "star", "text": "Intensive hydration"},
                    {"icon": "check", "text": "Clinically proven"}
                ],
                "footer": "Dermatologist tested.",
                "speech_bubble": "PRO"
            },
            "colors": {"primary": "#FFFFFF", "secondary": "#D1D5DB"} # Light text for dark background
        },
        {
            "id": "real_img_03_korean_test",
            "image_path": "data/outputs/job_62d14c3711f64ac0aefbf88310e52f8d/gpt_image_2_0.png",
            "subject_position": "bottom", # Manual metadata
            "preset": "top_headline_footer", # Corresponding preset
            "content": {
                "headline": "눈부신 광채 피부",
                "subcopy": "매일 아침 깨어나는 투명한 아름다움을 경험하세요.",
                "memo_card": ["베스트셀러\n오늘만 20% 할인!"],
                "footer": "온라인 및 전국 매장에서 만나보세요.",
                "speech_bubble": "신상품!"
            },
            "colors": {"primary": "#1E3A8A", "secondary": "#4B5563"} # Dark text for bright background
        }
    ]
    
    report_data = []
    
    for tc in test_cases:
        sc_id = tc["id"]
        preset = tc["preset"]
        img_path = Path(tc["image_path"])
        
        print(f"▶ Testing Scenario: {sc_id} (Preset: {preset}, Subject: {tc['subject_position']})")
        
        if not img_path.exists():
            print(f"  ❌ File not found: {img_path}")
            continue
            
        with Image.open(img_path) as img:
            canvas_w, canvas_h = img.size
            
        # Build components
        components = LAYOUT_PRESETS[preset](canvas_w, canvas_h, tc["content"], tc["colors"])
        
        # Build layout spec
        layout_spec = {
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "components": [c.model_dump() for c in components]
        }
        
        state = {
            "t2i_result": {"image_paths": [str(img_path)]},
            "poster_layout_spec": layout_spec,
            "job_id": f"test-real-integration-{sc_id}"
        }
        
        result = poster_renderer_node(state)
        
        render_result = result.get("render_result")
        if isinstance(render_result, str):
            render_result = json.loads(render_result)
        
        meta = render_result.get("metadata", {})
        quality_pass = meta.get("quality_pass", False)
        component_diagnostics = meta.get("component_diagnostics", [])
        
        final_path = render_result.get("final_image_path", "")
        
        has_contrast_warning = any(d.get("contrast_warning") for d in component_diagnostics)
        
        print(f"  ✅ RENDERED: {final_path}")
        if has_contrast_warning:
            print("  ⚠️ CONTRAST WARNING DETECTED!")
            
        report_data.append({
            "scenario_id": sc_id,
            "preset": preset,
            "subject_position": tc["subject_position"],
            "quality_pass": quality_pass,
            "has_contrast_warning": has_contrast_warning,
            "components": component_diagnostics,
            "output_path": final_path
        })
        
    out_file = Path("data/outputs/test-real-integration-poc/real_image_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report_data, indent=2))
    print(f"\n🎉 Integration Testing Complete! Report saved to {out_file}")

if __name__ == "__main__":
    run_integration_test()
