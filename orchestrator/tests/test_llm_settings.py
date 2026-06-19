import pytest

from orchestrator.app.llm.settings import LLMSettings


@pytest.mark.parametrize("value", ["abc", "", "  ", "0", "-1", "10.5"])
def test_llm_timeout_invalid_or_non_positive_values_fall_back(monkeypatch, value):
    monkeypatch.setenv("EASYADS_LLM_TIMEOUT_SECONDS", value)
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "30")

    assert LLMSettings.from_env().request_timeout_seconds == 30


def test_llm_timeout_accepts_positive_integer(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_TIMEOUT_SECONDS", "10")

    assert LLMSettings.from_env().request_timeout_seconds == 10


@pytest.mark.parametrize(
    ("name", "value", "attribute", "expected"),
    [
        ("EASYADS_LLM_MAX_RETRIES", "abc", "max_retries", 0),
        ("EASYADS_LLM_MAX_RETRIES", "-1", "max_retries", 0),
        ("EASYADS_LLM_MAX_RETRIES", "2", "max_retries", 2),
        ("EASYADS_LOCAL_LLM_TIMEOUT_SECONDS", "0", "local_llm_timeout_seconds", 60),
        ("EASYADS_LOCAL_LLM_TIMEOUT_SECONDS", "15", "local_llm_timeout_seconds", 15),
        ("EASYADS_LOCAL_LLM_MAX_RETRIES", "bad", "local_llm_max_retries", 0),
        ("EASYADS_LOCAL_LLM_MAX_RETRIES", "3", "local_llm_max_retries", 3),
    ],
)
def test_llm_integer_envs_are_safely_parsed(monkeypatch, name, value, attribute, expected):
    monkeypatch.setenv(name, value)

    assert getattr(LLMSettings.from_env(), attribute) == expected


@pytest.mark.parametrize(("value", "expected"), [("bad", None), ("-1", None), ("0", 0), ("4", 4)])
def test_llm_api_call_override_is_non_negative(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_MAX_API_CALLS_PER_JOB_OVERRIDE", value)

    assert LLMSettings.from_env().max_api_calls_per_job_override == expected
