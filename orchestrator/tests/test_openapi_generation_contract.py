from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app


def test_generation_job_openapi_exposes_canonical_engine_and_run_mode_enums():
    schema = TestClient(create_app()).get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["GenerationJobCreateRequest"]
    properties = request_schema["properties"]

    public_engines = {"gpt_image_2", "flux2_klein_4b", "sd35_large"}
    assert set(properties["imageGenerationEngine"]["enum"]) == public_engines
    assert set(properties["requestedEngine"]["enum"]) == public_engines
    assert set(properties["t2iEngine"]["enum"]) == public_engines
    assert properties["runMode"]["$ref"].endswith("/GenerationRunMode")
    assert "sourceAssetId" in properties
    assert "referenceAssetId" in properties
