from pathlib import Path

from orchestrator.app.t2i.prompts import resolve_negative_prompt
from orchestrator.app.t2i.service import generate_image_v1


def _phrases(prompt: str) -> list[str]:
    return [item.strip().lower() for item in prompt.split(",")]


def test_common_negative_prompt_applies_when_user_prompt_empty():
    effective = resolve_negative_prompt(None, None)

    assert "text" in effective
    assert "watermark" in effective
    assert "broken typography" in effective
    assert "people where not requested" in effective


def test_restaurant_negative_prompt_merges_from_business_type():
    effective = resolve_negative_prompt(None, {"business_type": "restaurant"})

    assert "text" in effective
    assert "dirty table" in effective
    assert "unappetizing food" in effective


def test_food_alias_maps_to_restaurant_negative_prompt():
    effective = resolve_negative_prompt(None, {"business_type": "food"})

    assert "burnt food" in effective
    assert "rotten ingredients" in effective


def test_user_negative_prompt_appends_after_common_and_industry():
    effective = resolve_negative_prompt("bad lighting, text", {"business_type": "cafe"})

    assert "text" in effective
    assert "spilled drink" in effective
    assert "bad lighting" in effective


def test_duplicate_phrases_are_removed_case_insensitively():
    effective = resolve_negative_prompt("TEXT, text, watermark", {"business_type": "restaurant"})
    phrases = _phrases(effective)

    assert phrases.count("text") == 1
    assert phrases.count("watermark") == 1


def test_generate_image_v1_returns_mock_image_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Korean BBQ campaign poster background",
        width=512,
        height=512,
        metadata={"job_id": "job-1", "business_type": "restaurant"},
    )

    assert result.engine == "mock"
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "job-1" / "mock_0.png")]
    assert Path(result.image_paths[0]).exists()


def test_generate_image_v1_metadata_contains_job_and_effective_negative_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Cafe signature drink ad background",
        negative_prompt="bad crop",
        metadata={"job_id": "job-meta", "business_type": "beverage"},
    )

    assert result.metadata["job_id"] == "job-meta"
    assert result.metadata["requested_engine"] == "mock"
    assert result.metadata["effective_engine"] == "mock"
    assert "bad crop" in result.metadata["effective_negative_prompt"]
    assert "industry:cafe" in result.metadata["negative_prompt_sources"]
    assert result.metadata["business_type"] == "beverage"
    assert result.metadata["num_images"] == 1


def test_generate_image_v1_uses_job_scoped_output_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Retail product promo background",
        metadata={"job_id": "job-path", "business_type": "product"},
    )

    assert str(tmp_path / "job-path" / "mock_0.png") == result.image_paths[0]
