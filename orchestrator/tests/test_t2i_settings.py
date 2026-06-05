from orchestrator.app.t2i.settings import (
    is_flux_local_enabled,
    is_gpt_image_2_enabled,
    is_sd35_local_enabled,
    load_t2i_settings,
)


def test_default_settings_disable_external_t2i(monkeypatch):
    for key in [
        "EASYADS_ENABLE_EXTERNAL_T2I",
        "EASYADS_ENABLE_GPT_IMAGE_2",
        "EASYADS_ENABLE_SD35_LOCAL",
        "EASYADS_ENABLE_FLUX_LOCAL",
        "OPENAI_API_KEY",
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = load_t2i_settings()

    assert settings.enable_external_t2i is False
    assert settings.enable_gpt_image_2 is False
    assert settings.enable_sd35_local is False
    assert settings.enable_flux_local is False
    assert is_gpt_image_2_enabled(settings) is False
    assert is_sd35_local_enabled(settings) is False
    assert is_flux_local_enabled(settings) is False


def test_settings_do_not_expose_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    monkeypatch.setenv("HF_TOKEN", "hf-secret-value")

    dumped = load_t2i_settings().model_dump(mode="json")

    assert dumped["openai_api_key_present"] is True
    assert dumped["hf_token_present"] is True
    assert "sk-secret-value" not in str(dumped)
    assert "hf-secret-value" not in str(dumped)


def test_flux_enabled_only_by_explicit_env(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_FLUX_LOCAL", raising=False)
    assert is_flux_local_enabled(load_t2i_settings()) is False

    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "true")
    settings = load_t2i_settings()

    assert settings.enable_flux_local is True
    assert is_flux_local_enabled(settings) is True
    assert settings.flux_model_id == "black-forest-labs/FLUX.1-schnell"


def test_flux_max_sequence_length_is_clamped(monkeypatch):
    monkeypatch.setenv("EASYADS_FLUX_MAX_SEQUENCE_LENGTH", "999")
    assert load_t2i_settings().flux_max_sequence_length == 512

    monkeypatch.setenv("EASYADS_FLUX_MAX_SEQUENCE_LENGTH", "8")
    assert load_t2i_settings().flux_max_sequence_length == 64

