"""Deterministic normalization from provider image size to contract output size."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps
from pydantic import BaseModel, Field


class NativeOutputNormalizationResult(BaseModel):
    source_path: str
    source_width: int = Field(ge=1)
    source_height: int = Field(ge=1)
    target_width: int = Field(ge=1)
    target_height: int = Field(ge=1)
    fit_mode: str
    crop_box: list[int] = Field(min_length=4, max_length=4)
    resample_mode: str
    output_path: str
    output_sha256: str
    normalization_applied: bool


def normalize_native_output(
    *,
    source_path: Path,
    target_width: int,
    target_height: int,
    output_path: Path,
    fit_mode: str = "cover_center",
) -> NativeOutputNormalizationResult:
    if fit_mode != "cover_center":
        raise ValueError(f"unsupported_fit_mode:{fit_mode}")

    with Image.open(source_path) as source_image:
        working = source_image.convert("RGBA")
        source_width, source_height = working.size
        crop_box = _cover_center_crop_box(
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
        )
        normalized = ImageOps.fit(
            working,
            (target_width, target_height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(output_path)

    return NativeOutputNormalizationResult(
        source_path=source_path.as_posix(),
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
        fit_mode=fit_mode,
        crop_box=crop_box,
        resample_mode="lanczos",
        output_path=output_path.as_posix(),
        output_sha256=_sha256(output_path),
        normalization_applied=(source_width, source_height) != (target_width, target_height),
    )


def _cover_center_crop_box(
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> list[int]:
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = round(crop_height * target_ratio)
        left = max(0, (source_width - crop_width) // 2)
        top = 0
    else:
        crop_width = source_width
        crop_height = round(crop_width / target_ratio)
        left = 0
        top = max(0, (source_height - crop_height) // 2)
    right = min(source_width, left + crop_width)
    bottom = min(source_height, top + crop_height)
    return [left, top, right, bottom]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
