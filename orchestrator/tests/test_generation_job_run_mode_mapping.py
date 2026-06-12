"""Characterization test for run_mode -> t2i engine routing."""

from orchestrator.app.api.routers.generation_jobs import T2I_RUN_MODE_TO_ENGINE


def test_run_mode_mapping_matches_legacy_elif_chain():
    # Exact behavior of the elif chain this mapping replaced.
    expected = {
        "gpt_image_1_actual": "gpt_image_1",
        "gpt_image_1_smoke": "gpt_image_1",
        "gpt_image_2_actual": "gpt_image_2",
        "gpt_image_2_smoke": "gpt_image_2",
        "sd35_local": "sd35_large",
        "sd35_local_smoke": "sd35_large",
        "sd35_large_real": "sd35_large",
        "flux2_klein_4b": "flux2_klein_4b",
        "flux_local": "flux2_klein_4b",
        "flux_local_smoke": "flux2_klein_4b",
        "flux_schnell_real": "flux2_klein_4b",
        "flux": "flux2_klein_4b",
        "flux_smoke": "flux2_klein_4b",
    }
    assert T2I_RUN_MODE_TO_ENGINE == expected


def test_non_t2i_modes_not_in_mapping():
    for mode in ("mock_immediate", "graph_job"):
        assert mode not in T2I_RUN_MODE_TO_ENGINE
