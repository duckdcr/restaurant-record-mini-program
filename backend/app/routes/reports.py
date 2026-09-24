from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import ApiError, get_current_user, get_db
from ..models import Report, User
from ..services.reports import create_report
from ..storage import storage_for


router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    date_from: date
    date_to: date


@router.post("", status_code=status.HTTP_201_CREATED)
def post_report(
    payload: ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.date_from > payload.date_to:
        raise ApiError("INVALID_DATE_RANGE", "开始日期不能晚于结束日期", 422)
    report = create_report(
        db,
        user,
        payload.date_from,
        payload.date_to,
        storage_for(request.app.state.settings),
        request.app.state.settings.app_timezone,
    )
    return {
        "id": report.id,
        "date_from": report.date_from.isoformat(),
        "date_to": report.date_to.isoformat(),
        "download_url": f"/api/v1/reports/{report.id}/download",
    }


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = db.get(Report, report_id)
    if not report or report.owner_id != user.id:
        raise ApiError("REPORT_NOT_FOUND", "报表不存在", 404)
    try:
        content = storage_for(request.app.state.settings).read(report.storage_key)
    except FileNotFoundError:
        raise ApiError("REPORT_FILE_MISSING", "报表文件不存在，请重新生成", 404)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{Path(report.storage_key).name}"'},
    )
