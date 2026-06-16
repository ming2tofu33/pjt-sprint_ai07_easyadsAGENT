import json
from pprint import pprint
from orchestrator.app.rendering.asset_registry import select_asset

def print_result(scenario_name, asset, diag):
    print(f"\n▶ Testing {scenario_name}")
    print(f"  - asset_registry_used: {diag.get('asset_registry_used')}")
    print(f"  - requested_asset_id: {diag.get('requested_asset_id')}")
    print(f"  - selected_asset_id: {diag.get('selected_asset_id')}")
    print(f"  - asset_variant: {diag.get('asset_variant')}")
    print(f"  - asset_fallback_used: {diag.get('asset_fallback_used')}")
    if diag.get('asset_fallback_used'):
        print(f"  - asset_fallback_reason: {diag.get('asset_fallback_reason')}")
    print(f"  - asset_policy_reason: {diag.get('asset_policy_reason')}")
    if diag.get('validation_warnings'):
        print(f"  - validation_warnings: {diag.get('validation_warnings')}")

def run_tests():
    # Scenario 1: Explicit valid request
    asset, diag = select_asset(
        component_type="decorative_sticker",
        requested_asset_id="sticker_starburst_basic"
    )
    print_result("Scenario 1: Explicit sticker_starburst_basic", asset, diag)
    assert diag["selected_asset_id"] == "sticker_starburst_basic"

    # Scenario 2: Invalid asset request (Fallback cycle prevention check)
    asset, diag = select_asset(
        component_type="decorative_sticker",
        requested_asset_id="non_existent_asset"
    )
    print_result("Scenario 2: Fallback from non-existent requested asset", asset, diag)
    assert diag["asset_fallback_used"] == True

    # Scenario 3: Variant based mapping (sticker)
    asset, diag = select_asset(
        component_type="decorative_sticker",
        variant="underline_accent"
    )
    print_result("Scenario 3: Variant based mapping (underline_accent)", asset, diag)
    assert diag["selected_asset_id"] == "sticker_underline_accent_basic"

    # Scenario 4: Icon based mapping
    asset, diag = select_asset(
        component_type="icon_feature_list",
        variant="check"
    )
    print_result("Scenario 4: Icon mapping (check)", asset, diag)
    assert diag["selected_asset_id"] == "icon_check_basic"

    # Scenario 5: Template compatibility failure (Fallback)
    asset, diag = select_asset(
        component_type="decorative_sticker",
        requested_asset_id="sticker_starburst_basic",
        template_id="some_unsupported_template"
    )
    print_result("Scenario 5: Template compatibility failure", asset, diag)
    # starburst doesn't have fallback_asset_id so it completely fails to none.
    assert diag["unsupported_asset"] == True
    assert asset is None

    # Scenario 6: Backward compatibility (no asset_id or variant provided)
    asset, diag = select_asset(
        component_type="headline_block",
        requested_asset_id=None,
        variant=None
    )
    print_result("Scenario 6: Backward compatibility (headline_block)", asset, diag)
    assert diag["asset_registry_used"] == False

if __name__ == "__main__":
    run_tests()
