from pathlib import Path

from PIL import Image


def write_test_png(
    path: Path,
    *,
    size: tuple[int, int] = (64, 64),
    color: tuple[int, int, int] = (180, 120, 90),
) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path
