import json
from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
from orchestrator.app.schemas.text_layout import CopySpec, CopyItem

def create_state(subject_position, safe_zone, background_complexity, confidence):
    return {
        "job_id": "test-bbox",
        "renderer_mode": "poster_components",
        "image_analysis": {
            "subject_position": subject_position,
            "safe_zone": safe_zone,
            "background_complexity": background_complexity,
            "confidence": confidence,
            "source": "vlm"
        },
        "copy_spec": CopySpec(
            items=[
                CopyItem(text="Huge Headline Text", role="headline"),
                CopyItem(text="Some nice subcopy that follows", role="subheadline"),
                CopyItem(text="Visit us today", role="store_info")
            ]
        ).model_dump()
    }

def run_tests():
    scenarios = [
        # 1. safe_zone=left, subject_position=right -> headline/subcopy left adjustment
        ("right", "left", "low", 0.9, False, False),
        
        # 2. safe_zone=top, subject_position=bottom -> top placement, footer warning
        ("bottom", "top", "low", 0.9, False, False),
        
        # 3. background_complexity=high -> conservative/warning
        ("center", "center", "high", 0.9, False, False),
        
        # 4. confidence < 0.5 -> fallback
        ("right", "left", "low", 0.4, False, True),
        
        # 5. existing poster_layout_spec -> skipped
        ("right", "left", "low", 0.9, True, False)
    ]

    for i, (sub, safe, bg, conf, is_preserved, expect_fallback) in enumerate(scenarios, 1):
        print(f"\n▶ Testing Scenario {i}: sub={sub}, safe={safe}, bg={bg}, conf={conf}, preserved={is_preserved}")
        state = create_state(sub, safe, bg, conf)
        
        if is_preserved:
            state["poster_layout_spec"] = {"preserved": True}
            
        res = poster_layout_planner_node(state)
        diag = res.get("render_result", {}).get("metadata", {}).get("planner_diagnostics", {})
        
        skipped = diag.get("bbox_adjustment_skipped")
        fallback = diag.get("bbox_adjustment_fallback")
        applied = diag.get("image_aware_bbox_adjustment_applied")
        reason = diag.get("bbox_adjustment_reason")
        warnings = diag.get("planning_warnings", [])
        
        print(f"  - bbox_adjustment_skipped: {skipped}")
        print(f"  - bbox_adjustment_fallback: {fallback}")
        print(f"  - image_aware_bbox_adjustment_applied: {applied}")
        print(f"  - bbox_adjustment_reason: {reason}")
        if warnings:
            print(f"  - warnings: {warnings}")
            
        if is_preserved:
            assert skipped == True
            assert fallback == False or fallback == None # it doesn't set fallback if skipped early
        else:
            assert fallback == expect_fallback
            if not expect_fallback:
                assert applied == True
                
        # Check component diagnostics if not skipped
        if not is_preserved and not fallback:
            spec = res.get("poster_layout_spec", {})
            comps = spec.get("components", [])
            for c in comps:
                role = c.get("role")
                cdiag = c.get("diagnostics", {})
                print(f"    * Component {role}: c={c}")

if __name__ == "__main__":
    run_tests()
