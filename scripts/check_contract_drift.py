"""Fail when Web, BFF, and backend public generation contracts drift."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest  # noqa: E402
from orchestrator.app.t2i.contracts import public_engine_values  # noqa: E402

EXPECTED_ENGINES = {"gpt_image_2", "flux2_klein_4b", "sd35_large"}


def extract_array(path: Path, export_name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(export_name)}\s*=\s*\[([^]]+)]", text)
    if not match:
        raise AssertionError(f"{export_name} not found in {path}")
    return set(re.findall(r'["\']([^"\']+)["\']', match.group(1)))


def assert_request_contract() -> None:
    asset_id = "asset_" + "1" * 32
    request = GenerationJobCreateRequest(userInput="Create", sourceAssetId=asset_id, referenceAssetId="asset_" + "2" * 32)
    assert request.source_asset_id == asset_id
    for field in ("sourceImagePath", "referenceImagePath"):
        try:
            GenerationJobCreateRequest(userInput="Create", **{field: "data/private.png"})
        except ValidationError:
            continue
        raise AssertionError(f"legacy public field accepted: {field}")


def assert_typescript_contracts() -> None:
    for relative in ("apps/web/app/api/_schemas/generate.ts", "apps/bff/src/schemas/generation.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for asset_field in ("sourceAssetId", "referenceAssetId"):
            assert re.search(rf"{asset_field}\s*:\s*z\.string", text), f"{asset_field} missing from {relative}"
        for legacy_field in ("sourceImagePath", "referenceImagePath"):
            assert re.search(rf"{legacy_field}\s*:\s*z\.never", text), f"{legacy_field} is not rejected in {relative}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi", type=Path, required=True)
    args = parser.parse_args()
    schema = json.loads(args.openapi.read_text(encoding="utf-8"))
    backend = set(public_engine_values())
    web = extract_array(ROOT / "apps/web/lib/generation-engine.ts", "SUPPORTED_IMAGE_GENERATION_ENGINES")
    bff = extract_array(ROOT / "apps/bff/src/contracts/generation-engines.js", "imageGenerationEngines")
    assert backend == web == bff == EXPECTED_ENGINES, (backend, web, bff)
    assert "gpt_image_1" not in backend | web | bff
    assert_request_contract()
    assert_typescript_contracts()
    assert "GenerationJobCreateRequest" in schema.get("components", {}).get("schemas", {})
    print("contract drift check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
