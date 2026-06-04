from scripts.smoke_llm_adapter import _safe_smoke_call_result, run_smoke


def test_safe_smoke_call_result_does_not_store_raw_text():
    result = _safe_smoke_call_result(
        {
            "success": True,
            "error": None,
            "latency_ms": 12,
            "token_usage": None,
            "cost_estimate": None,
            "output": "x" * 500,
            "raw_text": "raw model response should not be stored",
            "metadata": {"api_key": "sk-secret", "safe": True},
        }
    )

    assert "raw model response" not in str(result)
    assert "sk-secret" not in str(result)
    assert result["raw_text_present"] is True
    assert result["metadata"]["safe"] is True
    assert len(result["output_preview"]) <= 240


def test_smoke_local_provider_dry_run_does_not_call_actual(tmp_path, monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b")

    report = run_smoke(
        provider="local_openai_compat",
        task="copy_candidate_generation",
        dry_run=True,
        confirm_actual=True,
        output_dir=tmp_path,
    )

    assert report["provider"] == "local_openai_compat"
    assert report["actual_call_attempted"] is False
    assert report["result"]["metadata"]["local_base_url_configured"] is True
    assert report["result"]["metadata"]["local_api_key_present"] is False
    assert "api_key_present" not in report["result"]["metadata"]
