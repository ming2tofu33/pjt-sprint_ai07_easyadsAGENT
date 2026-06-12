from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from scripts._actual_creative_pipeline import ActualCreativeInput, normalize_actual_input


def test_text_only_requires_user_text(tmp_path):
    with pytest.raises(ValidationError):
        ActualCreativeInput(case_id="case", input_mode="text_only", output_dir=str(tmp_path))


def test_image_only_requires_source(tmp_path):
    with pytest.raises(ValidationError):
        ActualCreativeInput(case_id="case", input_mode="image_only", output_dir=str(tmp_path))


def test_source_asset_id_is_not_supported_without_resolver(tmp_path):
    with pytest.raises(ValidationError):
        ActualCreativeInput(case_id="case", input_mode="image_only", source_asset_id="asset_123", output_dir=str(tmp_path))


def test_text_and_image_requires_text_and_source(tmp_path):
    image = tmp_path / "source.png"
    Image.new("RGB", (16, 16), "#ffffff").save(image)

    with pytest.raises(ValidationError):
        ActualCreativeInput(case_id="case", input_mode="text_and_image", source_image_path=str(image), output_dir=str(tmp_path))

    request = ActualCreativeInput(case_id="case", input_mode="text_and_image", user_text="cheesecake", source_image_path=str(image), output_dir=str(tmp_path))
    assert request.user_text == "cheesecake"


def test_normalize_actual_input_records_source_sha_and_provenance(tmp_path):
    image = tmp_path / "source.png"
    Image.new("RGB", (16, 16), "#ffffff").save(image)
    request = ActualCreativeInput(
        case_id="case",
        input_mode="image_only",
        source_image_path=str(image),
        source_provenance="actual_generated_reuse",
        output_dir=str(tmp_path),
    )

    evidence = normalize_actual_input(request, runtime=object(), case_dir=tmp_path / "case")

    assert evidence["source_image_sha256"]
    assert evidence["source_provenance"] == "actual_generated_reuse"
