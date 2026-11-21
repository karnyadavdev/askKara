import io
from typing import Protocol

from kara.config import get_settings

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_MAX_EDGE = 256
SIGNED_URL_TTL_SECONDS = 60


class AvatarError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AvatarStore(Protocol):
    async def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    async def signed_url(self, key: str) -> str: ...


class S3AvatarStore:
    def __init__(self, bucket: str, region: str):
        import boto3

        self._bucket = bucket
        self._client = boto3.client("s3", region_name=region)

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        import asyncio

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    async def signed_url(self, key: str) -> str:
        import asyncio

        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=SIGNED_URL_TTL_SECONDS,
        )


_store: AvatarStore | None = None
_store_loaded = False


def get_avatar_store() -> AvatarStore | None:
    global _store, _store_loaded
    if not _store_loaded:
        settings = get_settings()
        _store = S3AvatarStore(settings.avatar_bucket, settings.avatar_region) if settings.avatar_bucket else None
        _store_loaded = True
    return _store


def reset_avatar_store() -> None:
    global _store, _store_loaded
    _store = None
    _store_loaded = False


def process_avatar(raw: bytes) -> bytes:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise AvatarError("That file is not a readable image") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        img = background
    img.thumbnail((AVATAR_MAX_EDGE, AVATAR_MAX_EDGE), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
