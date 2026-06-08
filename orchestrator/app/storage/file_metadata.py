"""File metadata helpers for storage uploads."""

from __future__ import annotations

import mimetypes
import hashlib
from pathlib import Path


def guess_mime_type(path: str | Path) -> str | None:
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type


def get_file_size(path: str | Path) -> int | None:
    try:
        return Path(path).stat().st_size
    except OSError:
        return None


def get_file_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image_dimensions(path: str | Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
    except Exception:
        return None, None
    try:
        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return None, None
