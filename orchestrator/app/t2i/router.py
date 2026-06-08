"""T2I engine routing and health helpers."""

from __future__ import annotations

from typing import Any

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.base import BaseT2IEngine
from orchestrator.app.t2i.gpt_image2 import GPTImage2Engine
from orchestrator.app.t2i.graph_engines import get_graph_actual_t2i_engine
from orchestrator.app.t2i.engines.flux2_klein import normalize_flux2_klein_engine_key
from orchestrator.app.t2i.mock import MockT2IEngine


_mock_engine = MockT2IEngine()
class NotImplementedT2IEngine(BaseT2IEngine):
    """Explicit placeholder for engines that are planned but not wired yet."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason

    def load(self) -> None:
        return None

    def unload(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return False

    def health(self) -> dict[str, Any]:
        return {"available": False, "loaded": False, "reason": self.reason}

    def generate(self, request):
        raise RuntimeError(f"{self.name} is not available: {self.reason}")


def get_t2i_engine(name: str | None = None) -> BaseT2IEngine:
    """Return the configured T2I engine object without loading heavy models."""
    settings = get_t2i_settings()
    engine_name = normalize_flux2_klein_engine_key(name or settings.default_engine)
    if engine_name == "mock":
        return _mock_engine
    if engine_name == "gpt_image_2":
        return GPTImage2Engine(allow_api_call=settings.allow_api_calls)
    if engine_name == "sd35_large":
        return get_graph_actual_t2i_engine("sd35_large")
    if engine_name == "flux":
        return get_graph_actual_t2i_engine("flux")
    if engine_name == "flux2_klein_4b":
        return get_graph_actual_t2i_engine("flux2_klein_4b")
    return NotImplementedT2IEngine(engine_name, "unknown engine")


def get_t2i_health() -> dict[str, dict[str, Any]]:
    """Return health for all MVP T2I lanes."""
    settings = get_t2i_settings()
    gpt_image_2_engine = get_t2i_engine("gpt_image_2")
    gpt_image_2_health = gpt_image_2_engine.health()
    _mock_engine.load()
    return {
        "mock": _mock_engine.health(),
        "gpt_image_2": {
            **gpt_image_2_health,
            "configured_model": gpt_image_2_health.get("configured_model", settings.gpt_image_model),
        },
        "sd35_large": {
            **get_t2i_engine("sd35_large").health(),
            "model_id": settings.sd35_model_id,
        },
        "flux": {
            **get_t2i_engine("flux").health(),
            "model_id": settings.flux_model_id,
        },
        "flux2_klein_4b": {
            **get_t2i_engine("flux2_klein_4b").health(),
            "model_id": settings.flux2_klein_model_id,
        },
    }
