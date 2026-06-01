import pytest

from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage2ActualEngine
from orchestrator.app.t2i.engines.mock import MockGuardedT2IEngine
from orchestrator.app.t2i.engines.registry import get_t2i_engine
from orchestrator.app.t2i.engines.sd35_large import SD35LargeLocalEngine


def test_registry_constructs_engines_without_calls_or_loads():
    assert isinstance(get_t2i_engine("mock"), MockGuardedT2IEngine)
    assert isinstance(get_t2i_engine("gpt_image_2"), GPTImage2ActualEngine)
    assert isinstance(get_t2i_engine("sd35_large"), SD35LargeLocalEngine)


def test_registry_unknown_engine_raises_clear_error():
    with pytest.raises(ValueError, match="unknown T2I engine"):
        get_t2i_engine("unknown")

