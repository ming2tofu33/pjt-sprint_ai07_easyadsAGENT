from decimal import Decimal

from orchestrator.app.usage import pricing


def test_llm_cost_uses_configured_token_rates():
    catalog = {
        "llm": {
            "openai:gpt-4.1-mini": {
                "input_per_1m_tokens_usd": "0.40",
                "output_per_1m_tokens_usd": "1.60",
            }
        }
    }

    cost, metadata = pricing.calculate_llm_cost(
        provider="openai",
        model_name="gpt-4.1-mini",
        input_tokens=1000,
        output_tokens=500,
        catalog=catalog,
    )

    assert cost == Decimal("0.0012")
    assert metadata["cost_source"] == "configured_estimate"


def test_missing_t2i_price_is_unpriced_not_zero():
    cost, metadata = pricing.calculate_t2i_cost(
        provider="openai",
        model_name="gpt-image-2",
        image_count=3,
        catalog={},
    )

    assert cost is None
    assert metadata["cost_source"] == "unpriced"


def test_modal_cost_uses_gpu_seconds():
    cost, metadata = pricing.calculate_modal_cost(
        gpu_type="a10g",
        runtime_seconds="12.5",
        catalog={"modal": {"a10g": {"per_second_usd": "0.002"}}},
    )

    assert cost == Decimal("0.0250")
    assert metadata["cost_source"] == "configured_estimate"
