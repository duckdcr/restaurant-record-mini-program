from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User
from ..services.dashboard import build_dashboard


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    date: date,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return build_dashboard(db, date, request.app.state.settings.app_timezone)

