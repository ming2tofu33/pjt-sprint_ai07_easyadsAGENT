import importlib.util
import asyncio
import io
import sys
import types
from pathlib import Path

from fastapi import UploadFile


service_module = types.ModuleType("services.rembg_pipeline")
service_module.extract_mask_only = lambda path: None
sys.modules.setdefault("services.rembg_pipeline", service_module)
multipart_module = types.ModuleType("multipart")
multipart_module.__version__ = "test"
multipart_parser_module = types.ModuleType("multipart.multipart")
multipart_parser_module.parse_options_header = lambda value: (value, {})
sys.modules.setdefault("multipart", multipart_module)
sys.modules.setdefault("multipart.multipart", multipart_parser_module)
module_path = Path(__file__).parents[1] / "app" / "main.py"
spec = importlib.util.spec_from_file_location("vision_service_main", module_path)
vision_main = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(vision_main)


def test_cleanup_paths_removes_all_files(tmp_path):
    paths = [tmp_path / "input.png", tmp_path / "mask.png"]
    for path in paths:
        path.write_bytes(b"data")

    vision_main.cleanup_paths(paths)

    assert all(not path.exists() for path in paths)


def test_cleanup_paths_ignores_missing_files(tmp_path):
    vision_main.cleanup_paths([tmp_path / "missing.png", None])


def test_cleanup_paths_swallows_unlink_failure(monkeypatch, tmp_path):
    path = tmp_path / "input.png"
    path.write_bytes(b"data")
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(OSError("locked")))

    vision_main.cleanup_paths([path])


def test_remove_background_registers_cleanup_after_file_response(monkeypatch):
    class MaskImage:
        def save(self, path):
            Path(path).write_bytes(b"mask")

    monkeypatch.setattr(vision_main, "extract_mask_only", lambda path: MaskImage())
    upload = UploadFile(filename="input.png", file=io.BytesIO(b"input"))

    response = asyncio.run(vision_main.api_remove_background(upload))
    cleanup_targets = [Path(path) for path in response.background.args[0]]

    assert response.background is not None
    assert all(path.exists() for path in cleanup_targets)
    asyncio.run(response.background())
    assert all(not path.exists() for path in cleanup_targets)
