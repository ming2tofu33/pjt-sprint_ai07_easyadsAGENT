from orchestrator.app.graph.routers import route_after_tone_binding


def test_copy_mode_router_branches():
    assert route_after_tone_binding({"copy_generation_mode": "suggest_candidates"}) == "copy_candidate_generation"
    assert route_after_tone_binding({"copy_generation_mode": "auto_pilot"}) == "auto_pilot_copywriting"
    assert route_after_tone_binding({"copy_generation_mode": "custom_input"}) == "custom_copy_input"
    assert route_after_tone_binding({"copy_generation_mode": "no_copy"}) == "no_copy_bypass"
    assert route_after_tone_binding({"copy_generation_mode": None}) == "auto_pilot_copywriting"
