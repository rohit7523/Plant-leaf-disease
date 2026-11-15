from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import logging
import os
from utils import convert_image_to_base64_and_test, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Leaf Disease Detection API", version="1.1.0")

@app.post("/disease-detection-file")
async def disease_detection_file(file: UploadFile = File(...)):
    """Analyze an uploaded leaf photo. Raw uploads up to 200 MB are accepted;
    images are resized/compressed before being sent to the vision model."""
    try:
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Image exceeds the {MAX_UPLOAD_MB} MB upload limit.")
        result = convert_image_to_base64_and_test(contents)
        if not isinstance(result, dict) or not result:
            raise ValueError("The AI service returned an empty response.")
        if result.get("error"):
            raise ValueError(result["error"])
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("Image rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Disease detection failed")
        raise HTTPException(status_code=502, detail=f"AI image analysis failed: {str(exc)}") from exc
    finally:
        await file.close()

@app.get("/")
async def root():
    return {
        "message": "Leaf Disease Detection API",
        "version": "1.1.0",
        "status": "running",
        "max_upload_mb": MAX_UPLOAD_MB,
        "endpoint": "/disease-detection-file"
    }
