from copy import deepcopy


def make_asset_row(**overrides) -> dict[str, object]:
    row = {
        "id": "internal-uuid",
        "public_asset_id": "asset_" + "a" * 32,
        "kind": "source",
        "metadata": {"upload": {"status": "pending"}},
        "bucket": "test-bucket",
        "object_key": "test-key",
        "storage_provider": "r2",
    }
    row.update(overrides)
    return deepcopy(row)
