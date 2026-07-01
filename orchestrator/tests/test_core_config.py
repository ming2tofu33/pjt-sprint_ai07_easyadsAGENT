"""Tests for core config env loading and dotenv caching."""

from orchestrator.app.core import config
from orchestrator.app.core.config import _get_env, _load_dotenv


def test_load_dotenv_caches_file_parse(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n")
    _load_dotenv.cache_clear()

    first = _load_dotenv(env_file)
    assert first["FOO"] == "bar"

    # Mutate the file; the cached parse must be returned (process-lifetime cache).
    env_file.write_text("FOO=changed\n")
    second = _load_dotenv(env_file)
    assert second is first
    assert second["FOO"] == "bar"

    _load_dotenv.cache_clear()


def test_load_dotenv_missing_file_returns_empty(tmp_path):
    _load_dotenv.cache_clear()
    assert _load_dotenv(tmp_path / "does_not_exist.env") == {}
    _load_dotenv.cache_clear()


def test_get_env_prefers_live_os_environ(monkeypatch):
    monkeypatch.setenv("EASYADS_TEST_CONFIG_KEY", "from-os")
    assert _get_env("EASYADS_TEST_CONFIG_KEY", "default") == "from-os"
    # Changing os.environ must be visible immediately (no caching of env lookups).
    monkeypatch.setenv("EASYADS_TEST_CONFIG_KEY", "from-os-2")
    assert _get_env("EASYADS_TEST_CONFIG_KEY", "default") == "from-os-2"


def test_get_env_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("EASYADS_TEST_CONFIG_KEY_ABSENT", raising=False)
    assert _get_env("EASYADS_TEST_CONFIG_KEY_ABSENT", "fallback") == "fallback"


def test_get_env_does_not_read_docs_api_key_env(monkeypatch, tmp_path):
    key = "EASYADS_TEST_DOCS_API_KEY_ENV"
    monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "_load_dotenv", _load_dotenv)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "api_key.env").write_text(f"{key}=from-docs-file\n", encoding="utf-8")
    _load_dotenv.cache_clear()

    try:
        assert _get_env(key, "fallback") == "fallback"
    finally:
        _load_dotenv.cache_clear()
