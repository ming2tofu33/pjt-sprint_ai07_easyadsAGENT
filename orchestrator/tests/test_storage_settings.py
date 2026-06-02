from orchestrator.app.storage import settings


def test_asset_storage_backend_defaults_to_local_dev(monkeypatch):
    monkeypatch.delenv("EASYADS_ASSET_STORAGE_BACKEND", raising=False)

    assert settings.get_asset_storage_backend() == "local_dev"


def test_asset_storage_backend_accepts_r2(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "r2")

    assert settings.get_asset_storage_backend() == "r2"


def test_asset_storage_backend_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "weird")

    assert settings.get_asset_storage_backend() == "local_dev"
    assert settings.is_r2_upload_enabled() is False


def test_r2_readiness_reports_backend_validity(monkeypatch):
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "r22")

    readiness = settings.get_r2_readiness()

    assert readiness["backend"] == "local_dev"
    assert readiness["backend_valid"] is False
