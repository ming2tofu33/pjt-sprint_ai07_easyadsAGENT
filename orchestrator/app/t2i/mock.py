"""Mock T2I engine for GPU/API-free development."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.base import BaseT2IEngine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


class MockT2IEngine(BaseT2IEngine):
    """Generate deterministic placeholder images for wrapper tests."""

    name = "mock"

    def __init__(self) -> None:
        self._loaded = False

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def health(self) -> dict:
        return {"available": True, "loaded": self.is_loaded()}

    def generate(self, request: T2IRequest) -> T2IResult:
        started = time.perf_counter()
        if not self.is_loaded():
            self.load()

        output_dir = Path(request.output_dir) if request.output_dir else get_t2i_settings().output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths: list[str] = []
        for index in range(request.num_images):
            path = output_dir / f"mock_{index}.png"
            self._write_placeholder(path, request, index)
            image_paths.append(str(path))

        return T2IResult(
            engine=self.name,
            image_paths=image_paths,
            seed=request.seed,
            latency_ms=int((time.perf_counter() - started) * 1000),
            width=request.width,
            height=request.height,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            metadata={**request.metadata, "quality": request.quality, "num_images": request.num_images},
            error=None,
        )

    def _write_placeholder(self, path: Path, request: T2IRequest, index: int) -> None:
        image = Image.new("RGB", (request.width, request.height), "#1F2937")
        draw = ImageDraw.Draw(image)
        font_large = _font(36)
        font_medium = _font(24)
        prompt_preview = request.prompt[:96]
        lines = [
            f"engine: {self.name}",
            f"size: {request.width}x{request.height}",
            f"image: {index}",
            f"prompt: {prompt_preview}",
        ]
        y = 48
        draw.rectangle((0, 0, request.width, min(request.height, 250)), fill="#111827")
        for idx, line in enumerate(lines):
            draw.text((48, y), line, fill="#F9FAFB", font=font_large if idx == 0 else font_medium)
            y += 48 if idx == 0 else 34
        draw.rectangle((48, request.height - 120, request.width - 48, request.height - 48), outline="#F59E0B", width=4)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ["C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()