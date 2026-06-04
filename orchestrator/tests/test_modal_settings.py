from orchestrator.app.modal import settings


def test_modal_execution_defaults_to_local_disabled(monkeypatch):
    monkeypatch.delenv("EASYADS_T2I_EXECUTION_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_MODAL_EXECUTION", raising=False)

    assert settings.get_t2i_execution_backend() == "local"
    assert settings.is_modal_execution_enabled() is False


def test_modal_execution_unknown_backend_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modall")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")

    readiness = settings.get_modal_readiness()

    assert settings.get_t2i_execution_backend() == "local"
    assert settings.is_modal_execution_enabled() is False
    assert readiness["backend_valid"] is False


def test_modal_readiness_redacts_tokens(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id-should-not-leak")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "secret-should-not-leak")

    readiness = settings.get_modal_readiness()
    rendered = str(readiness)

    assert readiness["enabled"] is True
    assert readiness["token_id_present"] is True
    assert readiness["token_secret_present"] is True
    assert "token-id-should-not-leak" not in rendered
    assert "secret-should-not-leak" not in rendered


def test_modal_result_transport_unknown_falls_back_to_inline_base64(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_RESULT_TRANSPORT", "weird")

    assert settings.get_modal_result_transport() == "inline_base64"


def test_modal_function_name_routes_real_model_modes(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_FUNCTION_NAME", "generate_image")

    assert settings.get_modal_function_name(run_mode="flux_local_smoke", engine="flux") == "generate_image"
    assert settings.get_modal_function_name(run_mode="flux_schnell_real", engine="flux") == "generate_flux_schnell_image"
    assert settings.get_modal_function_name(run_mode="sd35_large_real", engine="sd35_large") == "generate_sd35_large_image"

    monkeypatch.setenv("EASYADS_MODAL_FLUX_FUNCTION_NAME", "custom_flux")
    monkeypatch.setenv("EASYADS_MODAL_SD35_FUNCTION_NAME", "custom_sd35")

    assert settings.get_modal_function_name(run_mode="flux_schnell_real") == "custom_flux"
    assert settings.get_modal_function_name(run_mode="sd35_large_real") == "custom_sd35"
