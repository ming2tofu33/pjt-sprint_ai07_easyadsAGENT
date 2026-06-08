from orchestrator.app.modal.service import build_modal_t2i_request_from_job, is_modal_eligible_run_mode


def test_flux2_klein_modal_contract_uses_same_engine_key():
    row = {
        "public_job_id": "job_public",
        "workspace_id": "ws",
        "thread_id": "thread_uuid",
        "run_mode": "flux2_klein_4b",
        "engine": "flux2_klein_4b",
        "prompt_preview": "premium cafe background",
        "metadata": {"public_thread_id": "thread_public"},
    }

    request = build_modal_t2i_request_from_job(job_row=row)

    assert is_modal_eligible_run_mode("flux2_klein_4b") is True
    assert request.engine == "flux2_klein_4b"
    assert request.run_mode == "flux2_klein_4b"
    assert request.params["render_mode"] == "flux2_klein_4b"

