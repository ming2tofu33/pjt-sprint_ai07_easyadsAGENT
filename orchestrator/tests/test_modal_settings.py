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
