import uuid
from io import BytesIO
import io
from PIL import Image, ImageOps

from pathlib import Path

PROFILE_PICS_DIR = Path('app/media/profile')

def process_profile_pic(content: bytes) -> str:
    PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

    image = Image.open(io.BytesIO(content))
    img = ImageOps.fit(image, (300, 300), method=Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    filename = f"{uuid.uuid4().hex}.png"
    filepath = PROFILE_PICS_DIR / filename
    img.save(filepath, format="PNG")
    return filename

def delete_profile_pic(filename: str) -> None:
    filepath = PROFILE_PICS_DIR / filename
    if filepath.exists():
        filepath.unlink()