from scripts.smoke_llm_adapter import _safe_smoke_call_result


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
