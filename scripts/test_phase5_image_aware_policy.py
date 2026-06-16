import json
from pathlib import Path
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.schemas.text_layout import CopySpec, CopyItem

def create_state(subject_position, safe_zone, background_complexity, confidence):
    return {
        "job_id": "test-policy",
        "renderer_mode": "poster_components",
        "image_analysis": {
            "subject_position": subject_position,
            "safe_zone": safe_zone,
            "background_complexity": background_complexity,
            "confidence": confidence,
            "source": "vlm"
        },
        "copywriting_result": {
            "copy_spec": CopySpec(
                items=[
                    CopyItem(text="Headline", role="headline"),
                    CopyItem(text="Subcopy", role="subheadline")
                ]
            ).model_dump()
        }
    }

def run_tests():
    scenarios = [
        # Scenario 1: right / left / low / 0.9 -> editorial_left
        ("right", "left", "low", 0.9, "editorial_left", False),
        
        # Scenario 2: bottom / top / low / 0.9 -> top_headline_footer
        ("bottom", "top", "low", 0.9, "top_headline_footer", False),
        
        # Scenario 3: left / right / low / 0.9 -> center_stack (Fallback)
        ("left", "right", "low", 0.9, "center_stack", True),
        
        # Scenario 4: unknown / unknown / low / 0.4 -> center_stack (Fallback, confidence)
        ("unknown", "unknown", "low", 0.4, "center_stack", True),
        
        # Scenario 5: center / center / high / 0.9 -> center_stack (Conservative Fallback + Warning)
        ("center", "center", "high", 0.9, "center_stack", True),
        
        # Scenario 6: manual metadata preservation
        ("right", "left", "low", 0.9, "preserved", False)
    ]

    for i, (sub, safe, bg, conf, expected_preset, expect_fallback) in enumerate(scenarios, 1):
        print(f"\n▶ Testing Scenario {i}: sub={sub}, safe={safe}, bg={bg}, conf={conf}")
        state = create_state(sub, safe, bg, conf)
        
        if expected_preset == "preserved":
            state["poster_layout_spec"] = {"preserved": True}
        
        res = poster_layout_planner_node(state)
        diag = res.get("render_result", {}).get("metadata", {}).get("planner_diagnostics", {})
        
        actual_preset = diag.get("selected_preset")
        actual_fallback = diag.get("fallback_used")
        policy_reason = diag.get("policy_reason")
        warnings = diag.get("planning_warnings", [])
        
        if expected_preset == "preserved":
            preserved = diag.get("existing_layout_preserved")
            if preserved:
                print(f"  ✅ existing_layout_preserved: {preserved} (Expected)")
            else:
                print(f"  ❌ existing_layout_preserved: {preserved} (Expected: True)")
            continue
            
        if actual_preset == expected_preset:
            print(f"  ✅ selected_preset: {actual_preset} (Expected)")
        else:
            print(f"  ❌ selected_preset: {actual_preset} (Expected: {expected_preset})")
            
        if actual_fallback == expect_fallback:
            print(f"  ✅ fallback_used: {actual_fallback} (Expected)")
        else:
            print(f"  ❌ fallback_used: {actual_fallback} (Expected: {expect_fallback})")
            
        print(f"  ℹ️ policy_reason: {policy_reason}")
        if warnings:
            print(f"  ⚠️ warnings: {warnings}")

if __name__ == "__main__":
    run_tests()
