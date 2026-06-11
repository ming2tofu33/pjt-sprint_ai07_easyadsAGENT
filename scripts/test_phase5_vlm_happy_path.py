import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from orchestrator.app.llm.nodes.image_analysis import image_analysis_node
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.schemas.text_layout import CopySpec, CopyItem

def run_happy_path():
    print("🚀 Starting Phase 5.2 VLM Happy Path Test...")
    
    # test image
    image_path = "data/test_images/dark_product_shot.png"
    
    state = {
        "job_id": "test-vlm-happy-path",
        "renderer_mode": "poster_components",
        "rendering_engine": "python",
        "t2i_result": {"image_paths": [image_path]},
        "copywriting_result": {
            "copy_spec": CopySpec(
                items=[
                    CopyItem(text="프리미엄 미드나잇 퍼퓸", role="headline"),
                    CopyItem(text="어둠 속에서 깨어나는 감각", role="subheadline"),
                    CopyItem(text="지금 바로 경험해보세요.", role="body")
                ]
            ).model_dump()
        }
    }
    
    # 1. Run VLM Node
    print("▶ Running image_analysis_node...")
    res_analysis = image_analysis_node(state)
    state.update(res_analysis)
    
    diag_vlm = state.get("render_result", {}).get("metadata", {}).get("image_analysis_diagnostics", {})
    print(f"  ✅ image_analysis_source: {diag_vlm.get('image_analysis_source')}")
    print(f"  ✅ vlm_used: {diag_vlm.get('vlm_used')}")
    print(f"  ✅ subject_position: {diag_vlm.get('subject_position')}")
    print(f"  ✅ background_complexity: {diag_vlm.get('background_complexity')}")
    print(f"  ✅ safe_zone: {diag_vlm.get('safe_zone')}")
    print(f"  ✅ confidence: {diag_vlm.get('confidence')}")
    print(f"  ✅ fallback_used: {diag_vlm.get('fallback_used')}")
    if diag_vlm.get('fallback_used'):
        print(f"  ⚠️ fallback_reason: {diag_vlm.get('fallback_reason')}")
    
    # 2. Run Planner Node
    print("\n▶ Running poster_layout_planner_node...")
    res_planner = poster_layout_planner_node(state)
    state.update(res_planner)
    
    diag_planner = state.get("render_result", {}).get("metadata", {}).get("planner_diagnostics", {})
    print(f"  ✅ planner_used: {diag_planner.get('planner_used')}")
    print(f"  ✅ selected_preset: {diag_planner.get('selected_preset')}")
    
    # 3. Run Renderer Node
    print("\n▶ Running poster_renderer_node...")
    res_renderer = poster_renderer_node(state)
    state.update(res_renderer)
    
    render_meta = state.get("render_result", {}).get("metadata", {})
    quality_pass = render_meta.get("quality_pass")
    print(f"  ✅ quality_pass: {quality_pass}")
    
    out_img = state.get("final_image_path")
    print(f"  ✅ final_image_path: {out_img}")
    
    # Save Report
    report = {
        "used_image": image_path,
        "vlm_analysis": state.get("image_analysis"),
        "image_analysis_diagnostics": diag_vlm,
        "selected_preset": diag_planner.get('selected_preset'),
        "final_image_path": out_img,
        "quality_pass": quality_pass,
        "fallback_used": diag_vlm.get('fallback_used')
    }
    
    report_path = Path("data/outputs/test-vlm-happy-path/report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Test Complete! Report saved to {report_path}")
    
if __name__ == "__main__":
    run_happy_path()
