"""Guarded T2I engine registry."""

from __future__ import annotations

from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage1ActualEngine, GPTImage2ActualEngine
from orchestrator.app.t2i.engines.flux_local import FluxLocalEngine
from orchestrator.app.t2i.engines.flux2_klein import Flux2KleinEngine, normalize_flux2_klein_engine_key
from orchestrator.app.t2i.engines.mock import MockGuardedT2IEngine
from orchestrator.app.t2i.engines.sd35_large import SD35LargeLocalEngine


def get_t2i_engine(engine_name: str):
    engine_name = normalize_flux2_klein_engine_key(engine_name)
    if engine_name == "mock":
        return MockGuardedT2IEngine()
    if engine_name == "gpt_image_1":
        return GPTImage1ActualEngine()
    if engine_name == "gpt_image_2":
        return GPTImage2ActualEngine()
    if engine_name == "sd35_large":
        return SD35LargeLocalEngine()
    if engine_name in {"flux", "flux_local"}:
        return FluxLocalEngine()
    if engine_name == "flux2_klein_4b":
        return Flux2KleinEngine()
    raise ValueError(f"unknown T2I engine: {engine_name}")
