"""Lightweight image-aware layout analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from orchestrator.app.schemas.text_layout import ExclusionZone, ImageLayoutAnalysis, NormalizedBBox


def analyze_image_layout(
    image_path: str | Path,
    *,
    vision_pipeline_results: list[dict[str, Any]] | None = None,
    product_preserve_spec: dict[str, Any] | None = None,
    ocr_spans: list[dict[str, Any]] | None = None,
    output_dir: str | Path | None = None,
) -> ImageLayoutAnalysis:
    path = Path(image_path)
    with Image.open(path).convert("RGB") as image:
        width, height = image.size
        gray = ImageOps.grayscale(image)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        variance = gray.filter(ImageFilter.GaussianBlur(radius=6))
        saliency = ImageChops.difference(gray, variance).filter(ImageFilter.GaussianBlur(radius=2))
        thirds = _region_summaries(gray, edges, saliency)
        zones = _semantic_zones(vision_pipeline_results or [], product_preserve_spec or {}, ocr_spans or [])
        zones.extend(_saliency_zones(saliency, width, height))
        negative = _negative_space_regions(thirds)
        subject_side = _dominant_subject_side(thirds["saliency"])
        if output_dir:
            _write_debug_maps(Path(output_dir), gray, edges, saliency, zones, negative)
        return ImageLayoutAnalysis(
            canvas_width=width,
            canvas_height=height,
            exclusion_zones=zones,
            suggested_negative_space_regions=negative,
            dominant_subject_side=subject_side,
            edge_density_summary=thirds["edge"],
            local_variance_summary=thirds["variance"],
            saliency_summary=thirds["saliency"],
            luminance_summary=thirds["luminance"],
            analysis_confidence=0.72 if zones or negative else 0.45,
            metadata={"source": "lightweight_pil", "image_path": str(path)},
        )


def bbox_overlap_ratio(text_box: NormalizedBBox, zone: NormalizedBBox) -> float:
    left = max(text_box.x, zone.x)
    top = max(text_box.y, zone.y)
    right = min(text_box.x + text_box.w, zone.x + zone.w)
    bottom = min(text_box.y + text_box.h, zone.y + zone.h)
    if right <= left or bottom <= top:
        return 0.0
    return ((right - left) * (bottom - top)) / max(text_box.area_ratio(), 1e-6)


def _region_summaries(gray: Image.Image, edges: Image.Image, saliency: Image.Image) -> dict[str, dict[str, float]]:
    boxes = {
        "left": (0.0, 0.0, 0.40, 1.0),
        "center": (0.30, 0.0, 0.40, 1.0),
        "right": (0.60, 0.0, 0.40, 1.0),
        "top": (0.0, 0.0, 1.0, 0.35),
        "bottom": (0.0, 0.65, 1.0, 0.35),
    }
    return {
        "luminance": {key: _mean(gray, box) for key, box in boxes.items()},
        "edge": {key: _mean(edges, box) / 255 for key, box in boxes.items()},
        "saliency": {key: _mean(saliency, box) / 255 for key, box in boxes.items()},
        "variance": {key: _stddev(gray, box) / 255 for key, box in boxes.items()},
    }


def _mean(image: Image.Image, box: tuple[float, float, float, float]) -> float:
    crop = _crop(image, box)
    return float(ImageStat.Stat(crop).mean[0])


def _stddev(image: Image.Image, box: tuple[float, float, float, float]) -> float:
    crop = _crop(image, box)
    return float(ImageStat.Stat(crop).stddev[0])


def _crop(image: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    x, y, w, h = box
    return image.crop((round(x * width), round(y * height), round((x + w) * width), round((y + h) * height)))


def _semantic_zones(vision_results: list[dict[str, Any]], product_spec: dict[str, Any], ocr_spans: list[dict[str, Any]]) -> list[ExclusionZone]:
    zones: list[ExclusionZone] = []
    for source, items, zone_type in [("vision_pipeline", vision_results, "product"), ("ocr", ocr_spans, "ocr_artifact")]:
        for index, item in enumerate(items):
            bbox = item.get("bbox") or item.get("normalized_bbox")
            if isinstance(bbox, dict):
                zones.append(ExclusionZone(zone_id=f"{source}_{index}", zone_type=zone_type, bbox=NormalizedBBox(**bbox), confidence=float(item.get("confidence", 0.7)), hard_exclusion=True, source=source))
    bbox = product_spec.get("bbox") or product_spec.get("normalized_bbox")
    if isinstance(bbox, dict):
        zones.append(ExclusionZone(zone_id="product_preserve", zone_type="product", bbox=NormalizedBBox(**bbox), confidence=0.9, hard_exclusion=True, source="product_preserve_spec"))
    return zones


def _saliency_zones(saliency: Image.Image, width: int, height: int) -> list[ExclusionZone]:
    summaries = _region_summaries(saliency, saliency, saliency)["saliency"]
    zones: list[ExclusionZone] = []
    for side, value in summaries.items():
        if side in {"top", "bottom"} or value < 0.18:
            continue
        x = {"left": 0.0, "center": 0.30, "right": 0.60}[side]
        zones.append(ExclusionZone(zone_id=f"saliency_{side}", zone_type="high_saliency", bbox=NormalizedBBox(x=x, y=0.08, w=0.40, h=0.84), confidence=min(0.85, value * 2.5), hard_exclusion=False, source="saliency"))
    return zones[:2]


def _negative_space_regions(thirds: dict[str, dict[str, float]]) -> list[NormalizedBBox]:
    scores = {}
    for side, x in {"left": 0.06, "right": 0.52}.items():
        scores[side] = thirds["edge"][side] + thirds["variance"][side] + thirds["saliency"][side]
    ordered = sorted(scores, key=scores.get)
    return [NormalizedBBox(x=0.06 if side == "left" else 0.52, y=0.12, w=0.42, h=0.62) for side in ordered]


def _dominant_subject_side(saliency: dict[str, float]) -> str:
    side = max(("left", "center", "right"), key=lambda key: saliency.get(key, 0.0))
    return side if saliency.get(side, 0.0) > 0.10 else "unknown"


def _write_debug_maps(output_dir: Path, gray: Image.Image, edges: Image.Image, saliency: Image.Image, zones: list[ExclusionZone], negative: list[NormalizedBBox]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    saliency.save(output_dir / "analysis_saliency.png")
    edges.save(output_dir / "analysis_edges.png")
    for filename, boxes, color in [
        ("analysis_exclusion_zones.png", [zone.bbox for zone in zones], "red"),
        ("analysis_negative_space.png", negative, "green"),
    ]:
        overlay = ImageOps.colorize(gray, black="black", white="white").convert("RGB")
        draw = ImageDraw.Draw(overlay)
        width, height = overlay.size
        for bbox in boxes:
            draw.rectangle((bbox.x * width, bbox.y * height, (bbox.x + bbox.w) * width, (bbox.y + bbox.h) * height), outline=color, width=4)
        overlay.save(output_dir / filename)
