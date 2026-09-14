import uuid
from io import BytesIO
from PIL import Image, ImageOps

from pathlib import Path

PROFILE_PICS_DIR = Path('app/media/profile')

def process_profile_pic(image: Image.Image) -> Path:
    PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
    image = ImageOps.fit(image, (256, 256), Image.ANTIALIAS)
    filename = f"{uuid.uuid4().hex}.png"
    filepath = PROFILE_PICS_DIR / filename
    image.save(filepath, format='PNG')
    return filepath

def delete_profile_pic(filepath: Path) -> None:
    if filepath.exists():
        filepath.unlink()