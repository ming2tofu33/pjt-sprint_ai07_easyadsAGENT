"""Check the EasyAds uv development environment without external calls."""

from __future__ import annotations

import importlib
import os
import platform
import sys
from importlib import metadata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CORE_IMPORTS = [
    ("pydantic", "pydantic"),
    ("langgraph", "langgraph"),
    ("langchain_core", "langchain-core"),
    ("PIL", "Pillow"),
    ("openai", "openai"),
    ("fastapi", "fastapi"),
    ("orchestrator.app.graph.state", None),
    ("orchestrator.app.schemas.llm_marketing", None),
    ("orchestrator.app.schemas.vision", None),
]


def package_version(package_name: str | None) -> str:
    if not package_name:
        return "project"
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "unknown"


def check_import(module_name: str, package_name: str | None = None) -> tuple[bool, str]:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - exact import error is environment-specific
        return False, str(exc)
    return True, package_version(package_name)


def check_torch() -> None:
    print("\nOptional GPU check")
    try:
        torch = importlib.import_module("torch")
    except Exception:
        print("- torch: not installed (OK for CPU/core development)")
        return

    cuda_available = bool(torch.cuda.is_available())
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
    print(f"- torch: {getattr(torch, '__version__', 'unknown')}")
    print(f"- cuda_available: {cuda_available}")
    print(f"- device: {device_name}")


def main() -> int:
    print("EasyAds uv environment check")
    print(f"- python: {sys.version.split()[0]}")
    print(f"- executable: {sys.executable}")
    print(f"- platform: {platform.platform()}")
    print(f"- virtual_env: {os.environ.get('VIRTUAL_ENV') or 'not set'}")
    print(f"- uv_hint: {'yes' if 'UV' in ' '.join(os.environ) or os.environ.get('VIRTUAL_ENV') else 'unknown'}")

    failed: list[str] = []
    print("\nCore imports")
    for module_name, package_name in CORE_IMPORTS:
        ok, detail = check_import(module_name, package_name)
        status = "OK" if ok else "FAIL"
        print(f"- {module_name}: {status} ({detail})")
        if not ok:
            failed.append(module_name)

    check_torch()

    if failed:
        print("\nCore environment check failed:")
        for module_name in failed:
            print(f"- {module_name}")
        return 1

    print("\nCore environment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
