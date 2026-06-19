import pytest
from pydantic import ValidationError

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.t2i.contracts import public_engine_values


def test_openapi_exposes_generation_job_asset_and_engine_contract() -> None:
    schema = create_app().openapi()["components"]["schemas"]["GenerationJobCreateRequest"]
    properties = schema["properties"]
    assert "sourceAssetId" in properties
    assert "referenceAssetId" in properties
    for field in ("imageGenerationEngine", "requestedEngine", "t2iEngine"):
        assert set(properties[field]["enum"]) == set(public_engine_values())
    assert properties["runMode"]["$ref"].endswith("/GenerationRunMode")


@pytest.mark.parametrize("field", ["sourceImagePath", "referenceImagePath"])
def test_generation_job_rejects_legacy_public_path_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        GenerationJobCreateRequest(userInput="Create", **{field: "data/private.png"})
