from orchestrator.app.storage import settings


def test_r2_settings_default_to_local_dev(monkeypatch):
    monkeypatch.delenv("EASYADS_ASSET_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_R2_UPLOAD", raising=False)
    readiness = settings.get_r2_readiness()

    assert settings.get_asset_storage_backend() == "local_dev"
    assert settings.is_r2_upload_enabled() is False
    assert readiness["enabled"] is False
    assert readiness["access_key_id_present"] is False
    assert readiness["secret_access_key_present"] is False


def test_r2_readiness_reports_missing_requirements_without_secret_values(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.delenv("EASYADS_R2_BUCKET", raising=False)
    monkeypatch.delenv("EASYADS_R2_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key-value")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret-value")

    readiness = settings.get_r2_readiness()

    assert readiness["enabled"] is True
    assert "EASYADS_R2_BUCKET" in readiness["missing_requirements"]
    assert "EASYADS_R2_ENDPOINT_URL" in readiness["missing_requirements"]
    assert "key-value" not in str(readiness)
    assert "secret-value" not in str(readiness)


def test_public_url_mode_requires_public_base(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "public")
    monkeypatch.delenv("EASYADS_R2_PUBLIC_BASE_URL", raising=False)

    readiness = settings.get_r2_readiness()

    assert readiness["url_mode"] == "public"
    assert "EASYADS_R2_PUBLIC_BASE_URL" in readiness["missing_requirements"]


def test_signed_url_mode_does_not_require_public_base(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "signed")
    monkeypatch.delenv("EASYADS_R2_PUBLIC_BASE_URL", raising=False)

    readiness = settings.get_r2_readiness()

    assert readiness["url_mode"] == "signed"
    assert "EASYADS_R2_PUBLIC_BASE_URL" not in readiness["missing_requirements"]
