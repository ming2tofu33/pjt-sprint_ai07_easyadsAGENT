import json
from pprint import pprint
from orchestrator.app.llm.nodes.design_recommendation_node import design_recommendation_node

def create_mock_state(
    render_success=True,
    quality_pass=True,
    ia_quality_pass=True,
    safe_zone_valid=True,
    overlap_risk=False,
    final_overflow=False,
    contrast_warning=False,
    bg_complexity="low"
):
    return {
        "image_analysis": {
            "subject_position": "right",
            "safe_zone": "left",
            "background_complexity": bg_complexity
        },
        "render_result": {
            "metadata": {
                "render_success": render_success,
                "quality_pass": quality_pass,
                "template_diagnostics": {
                    "selected_template_id": "editorial_left_basic",
                    "selected_preset_name": "editorial_left",
                    "template_fallback_used": False
                },
                "asset_diagnostics": {
                    "asset_fallback_used": False
                },
                "image_aware_quality_diagnostics": {
                    "image_aware_quality_pass": ia_quality_pass,
                    "safe_zone_alignment_valid": safe_zone_valid,
                    "subject_overlap_risk": overlap_risk,
                    "confidence_policy_valid": True
                },
                "component_diagnostics": [
                    {
                        "final_overflow_detected": final_overflow,
                        "clipped_by_canvas": False,
                        "component_error": False,
                        "decorative_overlap_text": False,
                        "contrast_warning": contrast_warning
                    }
                ]
            }
        }
    }

def print_result(scenario_name, res):
    dr = res["render_result"]["metadata"]["design_recommendation"]
    print(f"\n▶ Testing {scenario_name}")
    print(f"  - Level: {dr['recommendation_level']}")
    print(f"  - Reason (EN): {dr['design_reason']}")
    print(f"  - Reason (KO): {dr['design_reason_ko']}")
    print(f"  - Warnings: {dr['warnings']}")
    if dr['fallback_recommendation']:
        print(f"  - Fallback Action: {dr['fallback_recommendation']['suggested_action']}")

def run_tests():
    # Scenario 1: use_as_is
    state = create_mock_state()
    res = design_recommendation_node(state)
    print_result("Scenario 1: use_as_is", res)
    assert res["render_result"]["metadata"]["design_recommendation"]["recommendation_level"] == "use_as_is"

    # Scenario 2: minor_review (Contrast warning)
    state = create_mock_state(contrast_warning=True)
    res = design_recommendation_node(state)
    print_result("Scenario 2: minor_review (Contrast warning)", res)
    assert res["render_result"]["metadata"]["design_recommendation"]["recommendation_level"] == "minor_review"

    # Scenario 3: retry_recommended (Overlap risk)
    state = create_mock_state(ia_quality_pass=False, overlap_risk=True)
    res = design_recommendation_node(state)
    print_result("Scenario 3: retry_recommended (Overlap risk)", res)
    assert res["render_result"]["metadata"]["design_recommendation"]["recommendation_level"] == "retry_recommended"

    # Scenario 4: manual_review_required (Overflow)
    state = create_mock_state(quality_pass=False, final_overflow=True)
    res = design_recommendation_node(state)
    print_result("Scenario 4: manual_review_required (Overflow)", res)
    assert res["render_result"]["metadata"]["design_recommendation"]["recommendation_level"] == "manual_review_required"

    # Scenario 6: Missing Diagnostics Defense
    state = {
        "image_analysis": {},
        "render_result": {"metadata": {}}
    }
    res = design_recommendation_node(state)
    print_result("Scenario 6: Missing Diagnostics Defense", res)
    # Should safely output manual_review_required because render_success=False by default or use_as_is depending on flags.
    # Actually render_success defaults to False in mock if missing, so it will be manual_review_required
    assert res["render_result"]["metadata"]["design_recommendation"]["recommendation_level"] == "manual_review_required"

if __name__ == "__main__":
    run_tests()
