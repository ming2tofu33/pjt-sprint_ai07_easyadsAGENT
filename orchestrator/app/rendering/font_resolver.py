"""Cross-platform font resolver for PIL rendering."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from PIL import ImageFont
from pydantic import BaseModel

from orchestrator.app.rendering.font_catalog import (
    font_path_for_face,
    get_font_face,
    normalize_family_id,
    resolve_font_face,
)


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

FONT_FAMILY = {
    "Pretendard": {
        "regular": "Pretendard-Regular.otf",
        "medium": "Pretendard-Medium.otf",
        "bold": "Pretendard-Bold.otf",
    },
    "GmarketSans": {
        "light": "GmarketSansTTFLight.ttf",
        "regular": "GmarketSansTTFMedium.ttf",
        "bold": "GmarketSansTTFBold.ttf",
    },
    "MaruBuri": {
        "light": "MaruBuri-Light.ttf",
        "regular": "MaruBuri-Regular.ttf",
        "bold": "MaruBuri-Bold.ttf",
    },
    "SCDream": {
        "regular": "SCDream_Regular.otf",
        "medium": "SCDream_Medium.otf",
        "bold": "SCDream_Bold.otf",
    },
    "NotoSansKR": {
        "regular": "NotoSansKR-Regular.ttf",
        "medium": "NotoSansKR-Medium.ttf",
        "bold": "NotoSansKR-Bold.ttf",
    },
    "BMDOHYEON": {
        "regular": "BMDOHYEON_ttf.ttf",
        "bold": "BMDOHYEON_ttf.ttf",
    },
    "BMJUA": {
        "regular": "BMJUA_ttf.ttf",
        "bold": "BMJUA_ttf.ttf",
    },
    "RIDIBatang": {
        "regular": "RIDIBatang.otf",
        "bold": "RIDIBatang.otf",
    }
}


class ResolvedFont(BaseModel):
    font_id: str
    family_id: str
    relative_path: str | None = None
    requested_weight: int
    resolved_weight: int
    source: Literal["bundled", "env_override", "system", "pil_default"]
    fallback_used: bool = False


def get_custom_font_path(family: str, weight: str | None) -> str | None:
    if family not in FONT_FAMILY:
        return None
    family_map = FONT_FAMILY[family]
    weight_key = "regular"
    if weight in {"bold", "700", "800", "900"}:
        weight_key = "bold"
    elif weight in {"medium", "500", "600"}:
        weight_key = "medium" if "medium" in family_map else "regular"
    elif weight in {"light", "100", "200", "300"}:
        weight_key = "light" if "light" in family_map else "regular"
    
    file_name = family_map.get(weight_key) or family_map.get("regular")
    if file_name:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        return str(project_root / "assets" / "fonts" / file_name)
    return None


def _weight_to_int(weight: str | int | None) -> int:
    if isinstance(weight, int):
        return weight
    if weight in {"bold", "700", "800", "900"}:
        return 700
    if weight in {"medium", "500", "600"}:
        return 500
    if weight in {"light", "100", "200", "300"}:
        return 300
    try:
        return int(str(weight))
    except Exception:
        return 400


@lru_cache(maxsize=256)
def _load_truetype_cached(path: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=max(1, int(size_px)))


def resolve_font(*, family_id: str, weight: int, size_px: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, ResolvedFont]:
    normalized_family = normalize_family_id(family_id)
    requested_weight = _weight_to_int(weight)
    face = get_font_face(normalized_family)
    if not face:
        try:
            face = resolve_font_face(normalized_family, requested_weight)
        except ValueError:
            face = None
    elif face.family_id != normalized_family:
        face = None
    if face is None:
        face = resolve_font_face(normalized_family, requested_weight)

    font_path = font_path_for_face(face)
    if font_path.exists():
        return _load_truetype_cached(str(font_path), size_px), ResolvedFont(
            font_id=face.font_id,
            family_id=face.family_id,
            relative_path=face.relative_path,
            requested_weight=requested_weight,
            resolved_weight=face.weight,
            source="bundled",
            fallback_used=False,
        )

    env_path = os.getenv("EASYADS_FONT_PATH")
    if env_path and Path(env_path).exists():
        return _load_truetype_cached(env_path, size_px), ResolvedFont(
            font_id=face.font_id,
            family_id=face.family_id,
            relative_path=None,
            requested_weight=requested_weight,
            resolved_weight=face.weight,
            source="env_override",
            fallback_used=True,
        )

    system_path = resolve_font_path(None)
    if system_path:
        return _load_truetype_cached(system_path, size_px), ResolvedFont(
            font_id=face.font_id,
            family_id=face.family_id,
            relative_path=None,
            requested_weight=requested_weight,
            resolved_weight=face.weight,
            source="system",
            fallback_used=True,
        )

    return ImageFont.load_default(), ResolvedFont(
        font_id=face.font_id,
        family_id=face.family_id,
        relative_path=None,
        requested_weight=requested_weight,
        resolved_weight=face.weight,
        source="pil_default",
        fallback_used=True,
    )


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
    if preferred:
        try:
            return resolve_font(family_id=preferred, weight=_weight_to_int(weight), size_px=size)[0]
        except Exception:
            pass

    preferred_path = None
    if preferred and preferred in FONT_FAMILY:
        preferred_path = get_custom_font_path(preferred, weight)
        
    if not preferred_path:
        preferred_path = preferred or os.getenv("EASYADS_FONT_PATH")
        if not preferred_path and weight in {"bold", "700", "800", "900"}:
            # Fallback to default Pretendard Bold instead of Malgun for our system if available
            fallback = get_custom_font_path("Pretendard", "bold")
            preferred_path = fallback if fallback and Path(fallback).exists() else "C:/Windows/Fonts/malgunbd.ttf"
        elif not preferred_path:
            # Global fallback
            fallback = get_custom_font_path("Pretendard", "regular")
            if fallback and Path(fallback).exists():
                preferred_path = fallback

    font_path = resolve_font_path(preferred_path)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=max(1, size))
        except Exception:
            pass
    return ImageFont.load_default()

