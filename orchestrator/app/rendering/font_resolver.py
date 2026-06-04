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

