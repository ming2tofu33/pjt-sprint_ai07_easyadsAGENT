from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.schemas.vision import ImageInputSpec
from orchestrator.app.vision.preprocess import preprocess_image
from orchestrator.app.vision.settings import VisionSettings


def _settings(tmp_path: Path) -> VisionSettings:
    return VisionSettings(upload_dir=tmp_path / "uploads", processed_dir=tmp_path / "processed")


def _image(path: Path, size=(120, 80), mode="RGB") -> Path:
    color = (200, 120, 80, 180) if mode == "RGBA" else (200, 120, 80)
    Image.new(mode, size, color).save(path)
    return path


def test_preprocess_resize_saves_original_preprocessed_and_preview(tmp_path):
    path = _image(tmp_path / "source.png", size=(600, 400))

    result = preprocess_image(ImageInputSpec(image_path=str(path), max_side=300), "vision-preprocess", settings=_settings(tmp_path))

    assert result.width == 300
    assert result.height == 200
    assert result.mode == "RGB"
    assert result.original_artifact_path
    assert Path(result.original_artifact_path).exists()
    assert Path(result.preprocessed_artifact_path).exists()
    assert result.preview_path and Path(result.preview_path).exists()
    assert tmp_path / "processed" in Path(result.preprocessed_artifact_path).parents


def test_preprocess_converts_rgba_to_rgb(tmp_path):
    path = _image(tmp_path / "source.png", size=(40, 40), mode="RGBA")

    result = preprocess_image(ImageInputSpec(image_path=str(path)), "vision-rgba", settings=_settings(tmp_path))

    assert result.mode == "RGB"
    assert result.metadata.has_alpha is True


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg", ".png", ".webp"])
def test_allowed_extensions(tmp_path, suffix):
    path = _image(tmp_path / f"source{suffix}", size=(40, 40))

    result = preprocess_image(ImageInputSpec(image_path=str(path)), f"vision-ext-{suffix[1:]}", settings=_settings(tmp_path))

    assert Path(result.preprocessed_artifact_path).exists()


def test_invalid_extension_and_missing_file_raise(tmp_path):
    bad = tmp_path / "source.gif"
    bad.write_bytes(b"not-an-image")

    with pytest.raises(ValueError):
        preprocess_image(ImageInputSpec(image_path=str(bad)), "vision-bad-ext", settings=_settings(tmp_path))

    with pytest.raises(FileNotFoundError):
        preprocess_image(ImageInputSpec(image_path=str(tmp_path / "missing.png")), "vision-missing", settings=_settings(tmp_path))


def test_relative_input_paths_resolve_from_project_root(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    upload_dir = project_root / "data" / "uploads"
    upload_dir.mkdir(parents=True)
    path = _image(upload_dir / "source.png", size=(40, 40))
    monkeypatch.setattr("orchestrator.app.vision.preprocess.PROJECT_ROOT", project_root)
    monkeypatch.chdir(tmp_path)

    result = preprocess_image(
        ImageInputSpec(image_path="data/uploads/source.png"),
        "vision-relative",
        settings=_settings(tmp_path),
    )

    assert result.metadata.original_path == str(path.resolve())
    assert Path(result.preprocessed_artifact_path).exists()


def test_center_crop_and_fit_with_padding(tmp_path):
    path = _image(tmp_path / "wide.png", size=(200, 100))
    settings = _settings(tmp_path)

    cropped = preprocess_image(
        ImageInputSpec(image_path=str(path), preprocess_mode="center_crop", target_width=80, target_height=80),
        "vision-crop",
        settings=settings,
    )
    padded = preprocess_image(
        ImageInputSpec(image_path=str(path), preprocess_mode="fit_with_padding", target_width=80, target_height=80),
        "vision-pad",
        settings=settings,
    )

    assert (cropped.width, cropped.height) == (80, 80)
    assert (padded.width, padded.height) == (80, 80)
