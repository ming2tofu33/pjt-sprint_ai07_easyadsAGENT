import time

import pytest

from orchestrator.app.api.schemas.brand_kits import BrandKitCreateRequest, BrandKitUpdateRequest
from orchestrator.app.brand_kits.service import (
    DEMO_USER_ID,
    create_brand_kit,
    get_brand_kit,
    get_current_brand_kit,
    reset_brand_kit_store_for_tests,
    update_brand_kit,
)


@pytest.fixture(autouse=True)
def reset_store():
    reset_brand_kit_store_for_tests()
    yield
    reset_brand_kit_store_for_tests()


def test_create_brand_kit_generates_id_and_demo_user_current():
    created = create_brand_kit(
        BrandKitCreateRequest(
            store_name="Moon Cafe",
            business_type="cafe",
            brand_colors=["#F6A5B8"],
        )
    )

    assert created.brand_kit_id.startswith("bk_")
    assert created.user_id == DEMO_USER_ID
    assert get_brand_kit(created.brand_kit_id) == created
    assert get_current_brand_kit() == created


def test_reset_brand_kit_store_for_tests_clears_store():
    created = create_brand_kit(BrandKitCreateRequest(store_name="Moon Cafe", business_type="cafe"))
    reset_brand_kit_store_for_tests()

    assert get_brand_kit(created.brand_kit_id) is None
    assert get_current_brand_kit() is None


def test_update_brand_kit_changes_fields_and_timestamp():
    created = create_brand_kit(
        BrandKitCreateRequest(
            user_id="user_1",
            store_name="Moon Cafe",
            business_type="cafe",
            brand_tones=["warm"],
            brand_colors=["#FFFFFF"],
        )
    )
    time.sleep(0.001)

    updated = update_brand_kit(
        created.brand_kit_id,
        BrandKitUpdateRequest(
            store_name="Sun Cafe",
            brand_tones=["premium"],
            brand_colors=[],
        ),
    )

    assert updated is not None
    assert updated.store_name == "Sun Cafe"
    assert updated.business_type == "cafe"
    assert updated.brand_tones == ["premium"]
    assert updated.brand_colors == []
    assert updated.updated_at != created.updated_at
    assert get_current_brand_kit("user_1") == updated


def test_update_missing_brand_kit_returns_none():
    result = update_brand_kit("bk_missing", BrandKitUpdateRequest(store_name="New"))
    assert result is None


def test_update_empty_store_or_business_type_fails():
    created = create_brand_kit(BrandKitCreateRequest(store_name="Moon Cafe", business_type="cafe"))

    with pytest.raises(ValueError):
        update_brand_kit(created.brand_kit_id, BrandKitUpdateRequest.model_construct(store_name=""))

    with pytest.raises(ValueError):
        update_brand_kit(created.brand_kit_id, BrandKitUpdateRequest.model_construct(business_type=""))
