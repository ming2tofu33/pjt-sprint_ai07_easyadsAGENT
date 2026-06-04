"""Vision Pipeline MVP settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestrator.app.core.config import PROJECT_ROOT, _get_bool, _get_env


@dataclass(frozen=True)
class VisionSettings:
    upload_dir: Path
    processed_dir: Path
    max_file_size_mb: int = 20
    max_image_pixels: int = 12_000_000
    default_max_side: int = 1536
    allowed_extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")
    save_preview: bool = True
    preview_max_side: int = 512

    @classmethod
    def from_env(cls) -> "VisionSettings":
        return cls(
            upload_dir=resolve_path(_get_env("VISION_UPLOAD_DIR", "data/uploads")),
            processed_dir=resolve_path(_get_env("VISION_PROCESSED_DIR", "data/processed")),
            max_file_size_mb=int(_get_env("VISION_MAX_FILE_SIZE_MB", "20") or "20"),
            max_image_pixels=int(_get_env("VISION_MAX_IMAGE_PIXELS", "12000000") or "12000000"),
            default_max_side=int(_get_env("VISION_DEFAULT_MAX_SIDE", "1536") or "1536"),
            save_preview=_get_bool("VISION_SAVE_PREVIEW", True),
            preview_max_side=int(_get_env("VISION_PREVIEW_MAX_SIDE", "512") or "512"),
        )


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_vision_settings() -> VisionSettings:
    return VisionSettings.from_env()
