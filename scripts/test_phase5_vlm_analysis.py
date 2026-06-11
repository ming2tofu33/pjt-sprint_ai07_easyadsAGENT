import json
import os
from pathlib import Path

from orchestrator.app.llm.nodes.image_analysis import image_analysis_node

def run_vlm_analysis_test():
    print("🚀 Starting Phase 5.2 VLM Image Analysis Test...")
    
    # We will test 3 scenarios
    # 1. Normal VLM extraction
    # 2. Manual preservation
    # 3. Fallback (no image or invalid)

    test_cases = [
        {
            "id": "vlm_analysis_01_real_image",
            "image_path": "data/test_images/dark_product_shot.png",
            "image_analysis": None # Should trigger VLM
        },
        {
            "id": "vlm_analysis_02_manual_preserved",
            "image_path": "data/test_images/dark_product_shot.png",
            "image_analysis": {
                "subject_position": "bottom",
                "source": "manual",
                "confidence": 1.0
            }
        },
        {
            "id": "vlm_analysis_03_fallback",
            "image_path": None, # Will trigger fallback
            "image_analysis": None
        }
    ]
    
    report_data = []
    
    for tc in test_cases:
        sc_id = tc["id"]
        
        print(f"\n▶ Testing Scenario: {sc_id}")
        
        # Build initial state
        state = {
            "renderer_mode": "poster_components",
            "job_id": f"test-phase5-vlm-{sc_id}"
        }
        
        if tc["image_path"]:
            state["t2i_result"] = {"image_paths": [tc["image_path"]]}
            
        if tc["image_analysis"]:
            state["image_analysis"] = tc["image_analysis"]
            
        # Run Node
        result = image_analysis_node(state)
        
        # Parse output
        analysis = result.get("image_analysis")
        render_result = result.get("render_result", {})
        if isinstance(render_result, str):
            render_result = json.loads(render_result)
            
        meta = render_result.get("metadata", {})
        diagnostics = meta.get("image_analysis_diagnostics", {})
        
        print(f"  ✅ subject_position: {diagnostics.get('subject_position')}")
        print(f"  ✅ source: {diagnostics.get('image_analysis_source')}")
        print(f"  ✅ vlm_used: {diagnostics.get('vlm_used')}")
        print(f"  ✅ fallback_used: {diagnostics.get('fallback_used')}")
        if diagnostics.get("fallback_used"):
            print(f"  ⚠️ fallback_reason: {diagnostics.get('fallback_reason')}")
        if diagnostics.get("existing_analysis_preserved"):
            print("  ⚠️ existing_analysis_preserved: True")
            
        report_data.append({
            "scenario_id": sc_id,
            "diagnostics": diagnostics,
            "analysis_data": analysis
        })
        
    out_dir = Path("data/outputs/test-phase5-poc")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "vlm_analysis_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Phase 5.2 Testing Complete! Report saved to {report_path}")

if __name__ == "__main__":
    run_vlm_analysis_test()
