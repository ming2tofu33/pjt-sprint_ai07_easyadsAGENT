import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

try:
    from app.services.rembg_pipeline import extract_mask_only
except ImportError:
    # Fallback if run from a different working directory
    from services.rembg_pipeline import extract_mask_only

app = FastAPI(title="Vision Service API")
logger = logging.getLogger(__name__)


def cleanup_paths(paths: list[str | Path | None]) -> None:
    for path in paths:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("failed to cleanup temp file", extra={"path": str(path)}, exc_info=True)


@app.post("/remove-background")
async def api_remove_background(file: UploadFile = File(...)):
    input_path = None
    mask_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_in:
            shutil.copyfileobj(file.file, tmp_in)
            input_path = tmp_in.name

        mask_image = extract_mask_only(input_path)

        mask_path = input_path.replace(".png", "_mask.png")
        mask_image.save(mask_path)

        return FileResponse(
            mask_path,
            media_type="image/png",
            background=BackgroundTask(cleanup_paths, [input_path, mask_path]),
        )
    except Exception as e:
        cleanup_paths([input_path, mask_path])
        raise HTTPException(status_code=500, detail=str(e))
