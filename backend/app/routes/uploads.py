import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..auth import ApiError, get_current_user, get_db
from ..models import Upload, User
from ..storage import storage_for


router = APIRouter(prefix="/uploads", tags=["uploads"])
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def detect_image(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise ApiError("IMAGE_TOO_LARGE", "图片不能超过10MB", 413)
    detected = detect_image(content)
    if not detected:
        raise ApiError("UNSUPPORTED_IMAGE", "仅支持 JPEG、PNG 或 WebP 图片", 415)
    mime_type, extension = detected
    storage = storage_for(request.app.state.settings)
    storage_key = storage.save(content, extension, content_type=mime_type)
    upload = Upload(
        owner_id=user.id,
        storage_key=storage_key,
        sha256=hashlib.sha256(content).hexdigest(),
        mime_type=mime_type,
        size_bytes=len(content),
        original_name=Path(file.filename or "image").name,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return {
        "id": upload.id,
        "sha256": upload.sha256,
        "mime_type": upload.mime_type,
        "size_bytes": upload.size_bytes,
    }
