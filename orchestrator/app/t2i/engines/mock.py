"""Mock guarded T2I engine adapter."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from PIL import Image

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput


class MockGuardedT2IEngine:
    engine_name = "mock"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "mock_guarded_0.png"
        Image.new("RGB", (request.width, request.height), "#E5E7EB").save(path)
        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=[path.as_posix()],
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={"api_call": False, **request.metadata},
        )

