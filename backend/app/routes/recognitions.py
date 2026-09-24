from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import ApiError, get_current_user, get_db
from ..models import Upload, User
from ..services.recognition import recognize_upload


router = APIRouter(prefix="/recognitions", tags=["recognitions"])


class RecognitionRequest(BaseModel):
    upload_id: int
    meal: Literal["breakfast", "lunch", "dinner", "snack"]
    menu_date: date


@router.post("")
async def recognize(
    payload: RecognitionRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    upload = db.get(Upload, payload.upload_id)
    if not upload or upload.owner_id != user.id:
        raise ApiError("UPLOAD_NOT_FOUND", "图片不存在", 404)
    return await recognize_upload(db, upload, request.app.state.settings, payload.meal, payload.menu_date)

