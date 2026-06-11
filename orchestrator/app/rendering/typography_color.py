"""Adaptive typography color and overlay helpers."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageFilter, ImageStat


COLOR_CANDIDATES = {
    "warm_dark_brown": "#4A3A31",
    "dark_neutral": "#514941",
    "near_black": "#111111",
    "soft_white": "#FFF8EF",
    "brand_brown": "#6B4F3B",
}


def relative_luminance_rgb(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        v = value / 255.0
        channels.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio_hex(foreground: str, background_rgb: tuple[int, int, int]) -> float:
    fg = hex_to_rgb(foreground)
    l1 = relative_luminance_rgb(fg)
    l2 = relative_luminance_rgb(background_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def analyze_background_region(image: Image.Image, bbox: tuple[int, int, int, int]) -> dict[str, float]:
    x, y, w, h = bbox
    crop = image.crop((max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h))).convert("RGB")
    if crop.width <= 0 or crop.height <= 0:
        return {"luminance_p10": 1.0, "luminance_p50": 1.0, "luminance_p90": 1.0, "variance": 0.0, "edge_density": 0.0, "dark_ratio": 0.0, "light_ratio": 1.0}
    lum = sorted(relative_luminance_rgb(pixel) for pixel in crop.resize((min(64, crop.width), min(64, crop.height))).getdata())
    p10 = lum[int(len(lum) * 0.10)]
    p50 = lum[int(len(lum) * 0.50)]
    p90 = lum[int(len(lum) * 0.90)]
    stat = ImageStat.Stat(crop.convert("L"))
    edges = crop.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edges).mean[0] / 255.0
    return {
        "luminance_p10": p10,
        "luminance_p50": p50,
        "luminance_p90": p90,
        "variance": (stat.stddev[0] / 255.0) ** 2,
        "edge_density": edge_mean,
        "dark_ratio": sum(1 for value in lum if value < 0.35) / len(lum),
        "light_ratio": sum(1 for value in lum if value > 0.70) / len(lum),
    }


def choose_text_color(image: Image.Image, bbox: tuple[int, int, int, int], *, role: str, preferred: str | None = None) -> dict[str, Any]:
    analysis = analyze_background_region(image, bbox)
    bg = _average_rgb(image, bbox)
    threshold = 3.0 if role == "headline" else 4.5
    candidates = [preferred] if preferred else []
    candidates.extend(COLOR_CANDIDATES.values())
    scored = [(color, contrast_ratio_hex(color, bg)) for color in candidates if color]
    color, contrast = max(scored, key=lambda item: item[1])
    overlay = "none"
    if contrast < threshold:
        overlay = "content_fit_plate" if analysis["light_ratio"] > 0.55 else "soft_gradient_veil"
        color = COLOR_CANDIDATES["warm_dark_brown"] if analysis["light_ratio"] > 0.55 else COLOR_CANDIDATES["soft_white"]
        contrast = contrast_ratio_hex(color, bg)
    if color.lower() in {"#ffffff", "#fff8ef"} and analysis["light_ratio"] > 0.55 and overlay == "none":
        color = COLOR_CANDIDATES["warm_dark_brown"]
        contrast = contrast_ratio_hex(color, bg)
    return {"text_color": color, "contrast_ratio": round(contrast, 2), "overlay_treatment": overlay, "background": analysis}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = str(value or "").strip().lstrip("#")
    if len(cleaned) != 6:
        return (255, 255, 255)
    return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))


def _average_rgb(image: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
    x, y, w, h = bbox
    crop = image.crop((max(0, x), max(0, y), min(image.width, x + w), min(image.height, y + h))).convert("RGB")
    if crop.width <= 0 or crop.height <= 0:
        return (255, 255, 255)
    mean = ImageStat.Stat(crop).mean
    return (int(mean[0]), int(mean[1]), int(mean[2]))
