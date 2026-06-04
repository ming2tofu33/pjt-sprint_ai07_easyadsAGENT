import sys
import types

from orchestrator.app.storage import r2_client


def test_create_r2_client_uses_s3v4_signature(monkeypatch):
    captured = {}

    boto3_module = types.ModuleType("boto3")

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    boto3_module.client = fake_client

    botocore_module = types.ModuleType("botocore")
    config_module = types.ModuleType("botocore.config")

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    config_module.Config = FakeConfig

    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setitem(sys.modules, "botocore", botocore_module)
    monkeypatch.setitem(sys.modules, "botocore.config", config_module)

    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-dev")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("EASYADS_R2_REGION", "auto")

    client = r2_client.create_r2_client()

    assert client is not None
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "https://example.r2.cloudflarestorage.com"
    assert captured["config"].kwargs["signature_version"] == "s3v4"
