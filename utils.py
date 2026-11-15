"""Image preparation and Groq analysis helpers."""
from dotenv import load_dotenv
load_dotenv()

import base64
import io
import os
import sys
import logging
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)
LEAF_DIR = Path(__file__).parent / "Leaf Disease"
sys.path.insert(0, str(LEAF_DIR))

try:
    from main import LeafDiseaseDetector
except ImportError as exc:
    raise ImportError(f"Could not import LeafDiseaseDetector: {exc}") from exc

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
# Groq documents a 20 MB maximum image input for Qwen vision. Keep the
# optimized JPEG well below that after base64 expansion.
MAX_GROQ_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2560


def prepare_image_for_groq(image_bytes: bytes) -> bytes:
    """Validate any common photo format and compress/resize it to JPEG."""
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Image is larger than the {MAX_UPLOAD_MB} MB upload limit.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            # Avoid decompression bombs from unusually large pixel dimensions.
            if source.width * source.height > 100_000_000:
                raise ValueError("Image dimensions are too large to process safely (over 100 megapixels).")
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Unsupported or damaged image. Please upload a JPG, PNG, or WEBP photo.") from exc

    image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
    quality = 88
    while True:
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
        optimized = output.getvalue()
        if len(optimized) <= MAX_GROQ_IMAGE_BYTES:
            logger.info("Prepared image: %.2f MB -> %.2f MB JPEG", len(image_bytes)/1024/1024, len(optimized)/1024/1024)
            return optimized
        if quality > 70:
            quality -= 6
        elif max(image.size) > 1280:
            image.thumbnail((int(image.width * 0.85), int(image.height * 0.85)), Image.Resampling.LANCZOS)
            quality = 82
        else:
            raise ValueError("Could not compress this image enough for the AI service. Please use a smaller photo.")


def test_with_base64_data(base64_image_string: str):
    detector = LeafDiseaseDetector()
    return detector.analyze_leaf_image_base64(base64_image_string)


def convert_image_to_base64_and_test(image_bytes: bytes):
    optimized_jpeg = prepare_image_for_groq(image_bytes)
    base64_string = base64.b64encode(optimized_jpeg).decode("utf-8")
    return test_with_base64_data(base64_string)
