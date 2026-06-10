"""Pixel text fitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class TextBlockMeasurement:
    lines: list[str]
    width: int
    height: int
    overflow_ratio: float
    fits: bool


def measure_text_block(text: str, *, font: ImageFont.ImageFont, max_width: int, max_lines: int, line_height: int) -> TextBlockMeasurement:
    lines = wrap_text_no_ellipsis(text, font=font, max_width=max_width, max_lines=max_lines)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines] or [0]
    width = max(widths)
    height = line_height * len(lines)
    full_lines = wrap_text_no_ellipsis(text, font=font, max_width=max_width, max_lines=999)
    overflow = max(0, len(full_lines) - max_lines)
    overflow_ratio = overflow / max(1, len(full_lines))
    return TextBlockMeasurement(lines=lines, width=width, height=height, overflow_ratio=overflow_ratio, fits=overflow == 0 and width <= max_width)


def fit_text_block_to_bbox(
    text: str,
    *,
    font_factory: Any,
    bbox_width: int,
    bbox_height: int,
    max_lines: int,
    max_size: int,
    min_size: int,
    line_height_ratio: float = 1.15,
) -> dict[str, Any]:
    for size in range(max_size, max(min_size - 1, 0), -1):
        font = font_factory(size)
        measurement = measure_text_block(text, font=font, max_width=bbox_width, max_lines=max_lines, line_height=int(size * line_height_ratio))
        if measurement.fits and measurement.height <= bbox_height:
            return {"fits": True, "font_size": size, "lines": measurement.lines, "overflow_ratio": 0.0}
    font = font_factory(min_size)
    measurement = measure_text_block(text, font=font, max_width=bbox_width, max_lines=max_lines, line_height=int(min_size * line_height_ratio))
    return {"fits": False, "font_size": min_size, "lines": measurement.lines, "overflow_ratio": max(measurement.overflow_ratio, 0.01)}


def wrap_text_no_ellipsis(text: str, *, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = str(text or "").split() or [str(text or "")]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]
