from pathlib import Path

from PIL import Image


def write_test_png(path: Path, *, size: tuple[int, int] = (96, 96), color=(180, 120, 90)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path
