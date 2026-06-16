import json
from pathlib import Path
from pprint import pprint

from orchestrator.app.llm.nodes.image_aware_quality_gate import image_aware_quality_gate_node

def run_scenario(name, state_override):
    state = {
        "image_analysis": {
            "safe_zone": "left",
            "subject_position": "right",
            "background_complexity": "low",
            "confidence": 0.9
        },
        "render_result": {
            "metadata": {
                "quality_pass": True,
                "planner_diagnostics": {
                    "image_aware_bbox_adjustment_applied": True
                }
            }
        },
        "poster_layout_spec": {
            "components": [
                {"type": "headline_block", "bbox": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.2}},
                {"type": "footer_panel", "bbox": {"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.1}}
            ]
        }
    }
    
    # Apply overrides
    if "image_analysis" in state_override:
        state["image_analysis"].update(state_override["image_analysis"])
    if "render_result" in state_override:
        state["render_result"]["metadata"].update(state_override["render_result"]["metadata"])
    if "components" in state_override:
        state["poster_layout_spec"]["components"] = state_override["components"]
        
    res = image_aware_quality_gate_node(state)
    diag = res["render_result"]["metadata"]["image_aware_quality_diagnostics"]
    
    print(f"\n▶ Testing {name}")
    print(f"  - image_aware_quality_pass: {diag['image_aware_quality_pass']}")
    print(f"  - safe_zone_alignment_valid: {diag['safe_zone_alignment_valid']}")
    print(f"  - subject_overlap_risk: {diag['subject_overlap_risk']}")
    print(f"  - confidence_policy_valid: {diag['confidence_policy_valid']}")
    print(f"  - background_complexity_warning: {diag['background_complexity_warning']}")
    if diag['placement_validation_warnings']:
        print(f"  - warnings: {diag['placement_validation_warnings']}")

def run_tests():
    # Scenario 1: Safe zone 일치 케이스 (pass)
    run_scenario("Scenario 1: Safe zone left (Pass)", {})
    
    # Scenario 2: Safe zone 불일치 케이스 (fail/warning)
    run_scenario("Scenario 2: Safe zone left but placed right", {
        "components": [
            {"type": "headline_block", "bbox": {"x": 0.6, "y": 0.1, "w": 0.3, "h": 0.2}}
        ]
    })
    
    # Scenario 3: Subject 침범 위험 케이스 (fail/warning)
    run_scenario("Scenario 3: Subject right but text overflows", {
        "components": [
            {"type": "headline_block", "bbox": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.2}} # x+w = 0.9 > 0.75
        ]
    })
    
    # Scenario 4: 낮은 confidence 정책 위반 케이스 (fail)
    run_scenario("Scenario 4: Low confidence but bbox adjusted", {
        "image_analysis": {"confidence": 0.4}
    })
    
    # Scenario 5: 고복잡도 배경 케이스 (warning)
    run_scenario("Scenario 5: High background complexity", {
        "image_analysis": {"background_complexity": "high"}
    })
    
    # Scenario 6: 기존 렌더링 실패와 연계 케이스
    run_scenario("Scenario 6: Quality Pass False", {
        "render_result": {"metadata": {"quality_pass": False}}
    })

if __name__ == "__main__":
    run_tests()
