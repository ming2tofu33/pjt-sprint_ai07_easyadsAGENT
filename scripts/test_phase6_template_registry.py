import json
from pprint import pprint
from orchestrator.app.rendering.template_registry import select_template

def print_result(scenario_name, tmpl, diag):
    print(f"\n▶ Testing {scenario_name}")
    print(f"  - template_registry_used: {diag.get('template_registry_used')}")
    print(f"  - requested_template_id: {diag.get('requested_template_id')}")
    print(f"  - selected_template_id: {diag.get('selected_template_id')}")
    print(f"  - selected_preset_name: {diag.get('selected_preset_name')}")
    print(f"  - template_fallback_used: {diag.get('template_fallback_used')}")
    if diag.get('template_fallback_used'):
        print(f"  - template_fallback_reason: {diag.get('template_fallback_reason')}")
    print(f"  - template_policy_reason: {diag.get('template_policy_reason')}")
    if diag.get('unsupported_components'):
        print(f"  - unsupported_components: {diag.get('unsupported_components')}")

def run_tests():
    # Scenario 1: Basic explicit request
    tmpl, diag = select_template(
        image_analysis={},
        planner_policy={},
        requested_template_id="editorial_left_basic",
        components_to_render=[{"type": "headline_block"}],
        aspect_ratio="1:1"
    )
    print_result("Scenario 1: Explicit editorial_left_basic", tmpl, diag)
    assert diag["selected_template_id"] == "editorial_left_basic"

    # Scenario 2: Invalid template request (Fallback)
    tmpl, diag = select_template(
        image_analysis={},
        planner_policy={},
        requested_template_id="non_existent_template",
        components_to_render=[{"type": "headline_block"}],
        aspect_ratio="1:1"
    )
    print_result("Scenario 2: Fallback from non-existent requested template", tmpl, diag)
    assert diag["template_fallback_used"] == True

    # Scenario 3: Image analysis based auto selection
    tmpl, diag = select_template(
        image_analysis={"subject_position": "right", "safe_zone": "left"},
        planner_policy={},
        requested_template_id=None,
        components_to_render=[{"type": "headline_block"}],
        aspect_ratio="1:1"
    )
    print_result("Scenario 3: Auto selection by image_analysis (editorial_left)", tmpl, diag)
    assert diag["selected_template_id"] == "editorial_left_basic"
    assert diag["template_policy_reason"] == "Image-aware policy selected editorial_left_basic"

    # Scenario 4: Unsupported component (Fallback and warning)
    tmpl, diag = select_template(
        image_analysis={"subject_position": "center"},
        planner_policy={},
        requested_template_id="hero_center_basic",
        components_to_render=[{"type": "headline_block"}, {"type": "some_unsupported_block"}],
        aspect_ratio="1:1"
    )
    print_result("Scenario 4: Unsupported component injection", tmpl, diag)
    assert diag["template_fallback_used"] == True
    assert "some_unsupported_block" in diag["unsupported_components"]

    # Scenario 5: Backward compatibility (No requested id, normal path)
    from orchestrator.app.llm.nodes.poster_layout_planner import poster_layout_planner_node
    state = {
        "image_analysis": {"subject_position": "bottom", "safe_zone": "top", "confidence": 0.9, "background_complexity": "low"},
        "copy_spec": {
            "items": [
                {"role": "headline", "text": "Hello"},
                {"role": "body", "text": "World"}
            ]
        },
        "ad_format_spec": {"width": 1080, "height": 1080}
    }
    
    res = poster_layout_planner_node(state)
    meta = res["render_result"]["metadata"]
    print(f"\n▶ Testing Scenario 5: Planner node backward compatibility")
    print(f"  - planner preset used: {meta['planner_diagnostics']['selected_preset']}")
    print(f"  - template diagnostics selected: {meta['template_diagnostics']['selected_template_id']}")
    assert meta['planner_diagnostics']['selected_preset'] == "top_headline_footer"
    assert meta['template_diagnostics']['selected_template_id'] == "top_headline_footer_basic"

if __name__ == "__main__":
    run_tests()
