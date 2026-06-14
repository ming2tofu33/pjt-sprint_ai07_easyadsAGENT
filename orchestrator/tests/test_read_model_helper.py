"""Tests for the generic state model reader."""

from orchestrator.app.graph.state import context_to_model, read_model
from orchestrator.app.schemas.llm_marketing import MarketingContext


def test_read_model_parses_dict_to_model():
    state = {"context": {"business_type": "cafe"}}
    ctx = read_model(state, "context", MarketingContext)
    assert isinstance(ctx, MarketingContext)
    assert ctx.business_type == "cafe"


def test_read_model_returns_existing_model_instance_untouched():
    existing = MarketingContext(business_type="이미 모델")
    state = {"context": existing}
    assert read_model(state, "context", MarketingContext) is existing


def test_read_model_missing_key_returns_empty_model():
    ctx = read_model({}, "context", MarketingContext)
    assert isinstance(ctx, MarketingContext)


def test_read_model_none_value_returns_empty_model():
    ctx = read_model({"context": None}, "context", MarketingContext)
    assert isinstance(ctx, MarketingContext)


def test_read_model_default_none_returns_none_when_absent():
    assert read_model({}, "context", MarketingContext, default=None) is None
    assert read_model({"context": None}, "context", MarketingContext, default=None) is None


def test_read_model_default_none_still_parses_present_dict():
    ctx = read_model({"context": {"business_type": "x"}}, "context", MarketingContext, default=None)
    assert isinstance(ctx, MarketingContext)
    assert ctx.business_type == "x"


def test_context_to_model_still_works_after_delegation():
    # Backward-compat: existing helper keeps its exact behavior.
    assert isinstance(context_to_model(None), MarketingContext)
    assert isinstance(context_to_model({"business_type": "cafe"}), MarketingContext)
    existing = MarketingContext(business_type="cafe")
    assert context_to_model(existing) is existing
