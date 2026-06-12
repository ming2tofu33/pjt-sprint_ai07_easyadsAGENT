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


def measure_text_with_tracking(draw: ImageDraw.ImageDraw, text: str, *, font: ImageFont.ImageFont, tracking_px: float = 0.0) -> float:
    if not text:
        return 0.0
    width = 0.0
    for index, char in enumerate(text):
        width += float(draw.textlength(char, font=font))
        if index < len(text) - 1:
            width += tracking_px
    return width


def draw_text_with_tracking(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: Any,
    tracking_px: float = 0.0,
) -> None:
    x, y = xy
    cursor = float(x)
    for char in text:
        draw.text((cursor, y), char, font=font, fill=fill)
        cursor += float(draw.textlength(char, font=font)) + tracking_px


def measure_text_block(text: str, *, font: ImageFont.ImageFont, max_width: int, max_lines: int, line_height: int, tracking_px: float = 0.0) -> TextBlockMeasurement:
    lines = wrap_text_no_ellipsis(text, font=font, max_width=max_width, max_lines=max_lines, tracking_px=tracking_px)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    widths = [measure_text_with_tracking(draw, line, font=font, tracking_px=tracking_px) for line in lines] or [0]
    width = int(max(widths))
    height = line_height * len(lines)
    full_lines = wrap_text_no_ellipsis(text, font=font, max_width=max_width, max_lines=999, tracking_px=tracking_px)
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
    letter_spacing_em: float = 0.0,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    low = max(1, min_size)
    high = max(low, max_size)
    while low <= high:
        size = (low + high) // 2
        font = font_factory(size)
        tracking_px = max(-2.0, min(8.0, size * letter_spacing_em))
        measurement = measure_text_block(text, font=font, max_width=bbox_width, max_lines=max_lines, line_height=int(size * line_height_ratio), tracking_px=tracking_px)
        if measurement.fits and measurement.height <= bbox_height:
            best = {"fits": True, "font_size": size, "lines": measurement.lines, "overflow_ratio": 0.0, "tracking_px": tracking_px}
            low = size + 1
        else:
            high = size - 1
    if best:
        return best
    font = font_factory(min_size)
    tracking_px = max(-2.0, min(8.0, min_size * letter_spacing_em))
    measurement = measure_text_block(text, font=font, max_width=bbox_width, max_lines=max_lines, line_height=int(min_size * line_height_ratio), tracking_px=tracking_px)
    return {"fits": False, "font_size": min_size, "lines": measurement.lines, "overflow_ratio": max(measurement.overflow_ratio, 0.01), "tracking_px": tracking_px, "fit_action": "manual_review"}


def wrap_text_no_ellipsis(text: str, *, font: ImageFont.ImageFont, max_width: int, max_lines: int, tracking_px: float = 0.0) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    raw = str(text or "")
    words = raw.split()
    if not words and raw:
        words = _split_korean_phrases(raw)
    if len(words) == 1 and draw.textlength(words[0], font=font) > max_width:
        words = list(words[0])
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = measure_text_with_tracking(draw, candidate, font=font, tracking_px=tracking_px)
        if width <= max_width or not current:
            current = candidate
            continue
        if _is_orphan_particle(word) and lines:
            current = f"{current}{word}"
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _split_korean_phrases(text: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for char in text:
        current += char
        if char in ",./·|-" or len(current) >= 4:
            tokens.append(current.strip())
            current = ""
    if current.strip():
        tokens.append(current.strip())
    return tokens or [text]


def _is_orphan_particle(text: str) -> bool:
    return text in {"은", "는", "이", "가", "을", "를", "과", "와", "의", "에", "로", "도", "만"}
