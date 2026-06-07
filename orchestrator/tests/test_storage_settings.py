from orchestrator.app.storage import settings


def test_asset_storage_backend_defaults_to_local_dev(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "")

    assert settings.get_asset_storage_backend() == "local_dev"


def test_asset_storage_backend_accepts_r2(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "r2")

    assert settings.get_asset_storage_backend() == "r2"


def test_asset_storage_backend_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "weird")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")

    assert settings.get_asset_storage_backend() == "local_dev"
    assert settings.is_r2_upload_enabled() is False


def test_r2_readiness_reports_backend_validity(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "r22")

    readiness = settings.get_r2_readiness()

    assert readiness["backend"] == "local_dev"
    assert readiness["backend_valid"] is False


def test_r2_upload_required_enables_r2_readiness_checks(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "")

    readiness = settings.get_r2_readiness()

    assert settings.is_r2_upload_enabled() is True
    assert readiness["enabled"] is True
    assert readiness["missing_requirements"] == [
        "EASYADS_R2_BUCKET",
        "EASYADS_R2_ENDPOINT_URL",
        "EASYADS_R2_ACCESS_KEY_ID",
        "EASYADS_R2_SECRET_ACCESS_KEY",
    ]
