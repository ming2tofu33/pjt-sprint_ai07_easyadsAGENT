from pydantic import ValidationError

from orchestrator.app.api.schemas.brand_kits import (
    BrandKitCreateRequest,
    BrandKitGetCurrentResponse,
    BrandProduct,
)
from orchestrator.app.api.schemas.common import EmptyState


def test_brand_kit_create_request_validation_and_json_dump():
    request = BrandKitCreateRequest(
        store_name="Moon Cafe",
        business_type="cafe",
        brand_colors=["#F6A5B8"],
        representative_products=[BrandProduct(name="Strawberry cake", is_representative=True)],
    )

    dumped = request.model_dump(mode="json")

    assert dumped["store_name"] == "Moon Cafe"
    assert dumped["brand_colors"] == ["#F6A5B8"]


def test_brand_kit_create_request_rejects_empty_required_fields():
    try:
        BrandKitCreateRequest(store_name=" ", business_type="cafe")
    except ValidationError:
        pass
    else:
        raise AssertionError("empty store_name should fail validation")


def test_brand_kit_get_current_empty_state():
    response = BrandKitGetCurrentResponse(
        has_brand_kit=False,
        empty_state=EmptyState(kind="brand_kit_empty", title="No brand kit", message="Create a brand kit."),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["has_brand_kit"] is False
    assert dumped["empty_state"]["kind"] == "brand_kit_empty"
