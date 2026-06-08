import os
import types

import pytest

from scripts import run_vlm_quality_gate_smoke as smoke


def test_vlm_quality_gate_smoke_rejects_modal_backend():
    args = types.SimpleNamespace(engine="flux2_klein_4b", backend="modal", actual=False)

    assert "modal_actual_forbidden_in_this_task" in smoke._missing_requirements(args)


def test_vlm_quality_gate_smoke_actual_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("EASYADS_VLM_ACTUAL", raising=False)
    args = types.SimpleNamespace(engine="flux2_klein_4b", backend="local_diffusers", actual=True)

    assert "EASYADS_VLM_ACTUAL=1" in smoke._missing_requirements(args)


def test_vlm_quality_gate_smoke_redacts_secret_like_metadata():
    redacted = smoke._redact_metadata({"hf_token": "secret", "safe": "visible"})

    assert redacted["hf_token_present"] is True
    assert "secret" not in str(redacted)
    assert redacted["safe"] == "visible"


@pytest.mark.actual
def test_quality_gate_actual_smoke_requires_opt_in():
    if os.getenv("EASYADS_VLM_ACTUAL") != "1":
        pytest.skip("actual smoke is opt-in")
