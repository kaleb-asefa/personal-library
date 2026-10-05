import uuid
from io import BytesIO
import io
from PIL import Image, ImageOps

import boto3
from app.config import settings
from starlette.concurrency import run_in_threadpool


def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None,
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value() if settings.s3_secret_access_key else None,
        endpoint_url=settings.s3_endpoint_url,
    )

def process_profile_pic(content: bytes) -> tuple[bytes, str]:

    image = Image.open(io.BytesIO(content))
    img = ImageOps.fit(image, (300, 300), method=Image.Resampling.LANCZOS)

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    filename = f"{uuid.uuid4().hex}.png"
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.read(), filename


def _upload_to_s3(content: bytes, key: str) -> None:
    s3_client = _get_s3_client()
    s3_client.upload_fileobj(
        Fileobj=BytesIO(content),
        Bucket=settings.s3_bucket_name,
        Key=key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )

def _delete_from_s3(key: str) -> None:
    s3_client = _get_s3_client()
    s3_client.delete_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
    )

async def upload_to_s3(content: bytes, filename: str) -> None:
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_upload_to_s3, content, key)

async def delete_from_s3(filename: str | None) -> None:
    if filename is None:
        return
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_delete_from_s3, key)