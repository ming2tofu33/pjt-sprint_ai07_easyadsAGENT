"""Deterministic reference style stub."""

from __future__ import annotations

from statistics import pstdev

from PIL import Image

from orchestrator.app.schemas.vision import ImagePreprocessResult, ReferenceStyleProfile


def extract_reference_style_stub(preprocess_result: ImagePreprocessResult) -> ReferenceStyleProfile:
    with Image.open(preprocess_result.preprocessed_artifact_path).convert("RGB") as image:
        thumb = image.copy()
        thumb.thumbnail((96, 96), Image.Resampling.LANCZOS)
        colors = dominant_colors(thumb)
        luminances = [relative_luminance(rgb) for rgb in thumb.getdata()]
        brightness = sum(luminances) / len(luminances) if luminances else 0.5
        contrast_value = pstdev(luminances) if len(luminances) > 1 else 0.0
        contrast_hint = "low" if contrast_value < 0.12 else "medium" if contrast_value < 0.24 else "high"
        layout_hint = layout_from_size(image.width, image.height)
        moods = mood_keywords(colors, brightness)
        palette = [rgb_to_hex(color) for color in colors]
    return ReferenceStyleProfile(
        color_palette=palette,
        dominant_colors_rgb=colors,
        brightness=brightness,
        contrast_hint=contrast_hint,
        mood_keywords=moods,
        layout_hint=layout_hint,
        typography_hint="deterministic_stub_no_text_analysis",
        background_style="reference_style_stub",
        ad_style_prompt=f"reference-inspired advertising style with {', '.join(palette[:3])} palette, {', '.join(moods)} mood, {layout_hint} layout",
        metadata={"stub": True, "vlm_used": False, "llm_used": False},
    )


def dominant_colors(image: Image.Image, count: int = 5) -> list[tuple[int, int, int]]:
    quantized = image.quantize(colors=count).convert("RGB")
    colors = quantized.getcolors(maxcolors=image.width * image.height) or []
    ranked = sorted(colors, key=lambda item: item[0], reverse=True)
    return [rgb for _, rgb in ranked[:count]]


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def layout_from_size(width: int, height: int) -> str:
    ratio = width / height
    if ratio < 0.8:
        return "vertical_story_like"
    if ratio > 1.25:
        return "wide_banner_like"
    return "square_feed_like"


def mood_keywords(colors: list[tuple[int, int, int]], brightness: float) -> list[str]:
    moods = ["bright" if brightness > 0.62 else "calm" if brightness < 0.38 else "balanced"]
    redish = any(r > g + 25 and r > b + 25 for r, g, b in colors)
    greenish = any(g > r + 20 and g > b + 20 for r, g, b in colors)
    warm = any(r > 160 and g > 110 and b < 120 for r, g, b in colors)
    if redish:
        moods.extend(["cute", "emotional"])
    if greenish:
        moods.extend(["natural", "fresh"])
    if warm:
        moods.append("warm")
    if brightness < 0.45:
        moods.extend(["premium", "minimal"])
    return list(dict.fromkeys(moods))[:5]


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)
