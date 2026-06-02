"""Cross-platform font resolver for PIL rendering."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFont


FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def resolve_font_path(preferred: str | None = None) -> str | None:
    candidates = [preferred, os.getenv("EASYADS_FONT_PATH"), *FONT_CANDIDATES]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def load_font(
    size: int,
    weight: str | None = None,
    preferred: str | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    preferred_path = preferred or os.getenv("EASYADS_FONT_PATH")
    if not preferred_path and weight in {"bold", "700", "800", "900"}:
        preferred_path = "C:/Windows/Fonts/malgunbd.ttf"

    font_path = resolve_font_path(preferred_path)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=max(1, size))
        except Exception:
            pass
    return ImageFont.load_default()
