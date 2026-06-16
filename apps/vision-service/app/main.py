import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
import io

try:
    from app.services.rembg_pipeline import extract_mask_only
except ImportError:
    # Fallback if run from a different working directory
    from services.rembg_pipeline import extract_mask_only

app = FastAPI(title="Vision Service API")

@app.post("/remove-background")
async def api_remove_background(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_in:
            shutil.copyfileobj(file.file, tmp_in)
            input_path = tmp_in.name
            
        mask_image = extract_mask_only(input_path)
        
        # Save to a bytes buffer to return
        img_byte_arr = io.BytesIO()
        mask_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        mask_path = input_path.replace(".png", "_mask.png")
        mask_image.save(mask_path)
        
        return FileResponse(mask_path, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
