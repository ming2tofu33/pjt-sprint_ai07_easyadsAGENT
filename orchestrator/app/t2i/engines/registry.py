"""Guarded T2I engine registry."""

from __future__ import annotations

from orchestrator.app.t2i.engines.gpt_image_2 import GPTImage2ActualEngine
from orchestrator.app.t2i.engines.mock import MockGuardedT2IEngine
from orchestrator.app.t2i.engines.sd35_large import SD35LargeLocalEngine


def get_t2i_engine(engine_name: str):
    if engine_name == "mock":
        return MockGuardedT2IEngine()
    if engine_name == "gpt_image_2":
        return GPTImage2ActualEngine()
    if engine_name == "sd35_large":
        return SD35LargeLocalEngine()
    raise ValueError(f"unknown T2I engine: {engine_name}")

