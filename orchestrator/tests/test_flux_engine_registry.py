from orchestrator.app.t2i.engines.flux_local import FluxLocalEngine
from orchestrator.app.t2i.engines.registry import get_t2i_engine


def test_flux_registry_aliases_construct_without_model_load():
    assert isinstance(get_t2i_engine("flux"), FluxLocalEngine)
    assert isinstance(get_t2i_engine("flux_local"), FluxLocalEngine)
