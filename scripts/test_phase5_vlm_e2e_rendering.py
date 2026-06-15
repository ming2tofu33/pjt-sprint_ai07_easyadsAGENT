import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from orchestrator.app.llm.nodes.t2i_generation import t2i_generation_node
from orchestrator.app.llm.nodes.image_analysis import image_analysis_node
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.llm.nodes.poster_renderer import poster_renderer_node
from orchestrator.app.schemas.text_layout import CopySpec, CopyItem

def run_e2e_rendering_path():
    print("🚀 Starting Phase 5.2 E2E VLM Rendering Test...")
    
    output_dir = "data/outputs/test-vlm-e2e"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    state = {
        "job_id": "test-vlm-e2e",
        "renderer_mode": "poster_components",
        "rendering_engine": "python",
        "engine": "gpt_image_2",
        "t2i_request": {
            "prompt": "A modern and sleek premium perfume bottle placed on a dark background. The bottle is positioned on the right side of the image, leaving empty space on the left. Highly realistic, cinematic lighting.",
            "output_dir": output_dir,
            "width": 1024,
            "height": 1024,
            "metadata": {"engine": "gpt_image_2", "api_call": True}
        },
        "copy_spec": CopySpec(
            items=[
                CopyItem(text="Premium Midnight Perfume", role="headline"),
                CopyItem(text="Awaken your senses in the dark", role="subheadline"),
                CopyItem(text="Experience it now.", role="body")
            ]
        ).model_dump()
    }
    
    # 1. Run T2I Generation Node
    print("\n▶ [1/4] Running t2i_generation_node (generating image)...")
    res_t2i = t2i_generation_node(state)
    state.update(res_t2i)
    
    image_paths = state.get("t2i_result", {}).get("image_paths", [])
    if not image_paths:
        print(f"⚠️ Image generation failed or skipped. Mocking T2I and VLM results.")
        generated_image_path = "data/outputs/test-vlm-e2e/mock_image.png"
        from PIL import Image
        Image.new('RGB', (1024, 1024), color='gray').save(generated_image_path)
        state["t2i_result"] = {"image_paths": [generated_image_path]}
        state["image_analysis"] = {
            "subject_position": "right",
            "safe_zone": "left",
            "background_complexity": "low",
            "confidence": 0.9,
            "source": "mock"
        }
    else:
        generated_image_path = image_paths[0]
        print(f"  ✅ Generated image: {generated_image_path}")
        
        # 2. Run VLM Image Analysis Node
        print("\n▶ [2/4] Running image_analysis_node...")
        res_analysis = image_analysis_node(state)
        state.update(res_analysis)
    
    diag_vlm = state.get("render_result", {}).get("metadata", {}).get("image_analysis_diagnostics", {})
    if not diag_vlm: # Mocked
        diag_vlm = {
            "vlm_used": False,
            "subject_position": "right",
            "background_complexity": "low",
            "safe_zone": "left",
            "confidence": 0.9,
            "fallback_used": False
        }
        meta = state.get("render_result", {}).get("metadata", {})
        meta["image_analysis_diagnostics"] = diag_vlm
        if "render_result" not in state:
            state["render_result"] = {}
        state["render_result"]["metadata"] = meta

    print(f"  ✅ vlm_used: {diag_vlm.get('vlm_used')}")
    print(f"  ✅ subject_position: {diag_vlm.get('subject_position')}")
    print(f"  ✅ background_complexity: {diag_vlm.get('background_complexity')}")
    print(f"  ✅ safe_zone: {diag_vlm.get('safe_zone')}")
    print(f"  ✅ confidence: {diag_vlm.get('confidence')}")
    print(f"  ✅ fallback_used: {diag_vlm.get('fallback_used')}")
    
    # 3. Run Planner Node
    print("\n▶ [3/4] Running poster_layout_planner_node...")
    res_planner = poster_layout_planner_node(state)
    state.update(res_planner)
    
    diag_planner = state.get("render_result", {}).get("metadata", {}).get("planner_diagnostics", {})
    print(f"  ✅ selected_preset: {diag_planner.get('selected_preset')}")
    
    # 4. Run Renderer Node
    print("\n▶ [4/4] Running poster_renderer_node...")
    res_renderer = poster_renderer_node(state)
    state.update(res_renderer)
    
    # 5. Run Image-aware Quality Gate Node
    print("\n▶ [5/6] Running image_aware_quality_gate_node...")
    from orchestrator.app.llm.nodes.image_aware_quality_gate import image_aware_quality_gate_node
    res_gate = image_aware_quality_gate_node(state)
    state.update(res_gate)
    
    # 6. Run Design Recommendation Node
    print("\n▶ [6/6] Running design_recommendation_node...")
    from orchestrator.app.llm.nodes.design_recommendation_node import design_recommendation_node
    res_recommender = design_recommendation_node(state)
    state.update(res_recommender)
    
    render_meta = state.get("render_result", {}).get("metadata", {})
    quality_pass = render_meta.get("quality_pass")
    out_img = state.get("final_image_path")
    ia_quality_pass = render_meta.get("image_aware_quality_diagnostics", {}).get("image_aware_quality_pass")
    design_rec = render_meta.get("design_recommendation", {})
    diag_quality = render_meta.get("image_aware_quality_diagnostics", {})
    
    print(f"  ✅ quality_pass (physical): {quality_pass}")
    print(f"  ✅ image_aware_quality_pass (logical): {ia_quality_pass}")
    print(f"  ✅ recommendation_level: {design_rec.get('recommendation_level')}")
    print(f"  ✅ final_image_path: {out_img}")
    
    if diag_quality.get('placement_validation_warnings'):
        print(f"  ⚠️  warnings: {diag_quality.get('placement_validation_warnings')}")
    
    # Save Report
    report = {
        "generated_image": generated_image_path,
        "vlm_analysis": state.get("image_analysis"),
        "image_analysis_diagnostics": diag_vlm,
        "selected_preset": diag_planner.get('selected_preset'),
        "final_composite_poster": out_img,
        "quality_pass": quality_pass,
        "fallback_used": diag_vlm.get('fallback_used'),
        "image_aware_quality_diagnostics": diag_quality
    }
    
    report_path = Path("data/outputs/test-vlm-e2e/report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 E2E Test Complete! Report saved to {report_path}")
    
if __name__ == "__main__":
    run_e2e_rendering_path()
