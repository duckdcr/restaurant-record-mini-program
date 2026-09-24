from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import ApiError, get_current_user, get_db
from ..models import Sample, User
from ..services.samples import (
    create_sample,
    dispose_sample,
    list_samples,
    serialize_sample,
    soft_delete_sample,
)


router = APIRouter(prefix="/samples", tags=["samples"])


class FieldEvidence(BaseModel):
    raw_value: str | float | None = None
    source: Literal["ai", "default", "manual", "menu_match"]
    confidence: float | None = Field(default=None, ge=0, le=1)


class SampleCreate(BaseModel):
    menu_item_id: int | None = None
    dish_name: str = Field(min_length=1, max_length=160)
    meal: Literal["breakfast", "lunch", "dinner", "snack"]
    sampled_at: datetime
    amount_g: float = Field(gt=0, le=5000)
    temperature_c: float = Field(ge=-30, le=100)
    note: str = Field(default="", max_length=2000)
    upload_id: int
    recognition_run_id: int | None = None
    fields: dict[str, FieldEvidence]
    confirmed_fields: list[str] = []


class DisposalCreate(BaseModel):
    method: Literal["discard", "retain_for_test", "quarantine"]
    note: str = Field(default="", max_length=2000)
    reviewer_name: str = Field(min_length=1, max_length=80)


def require_sample(db: Session, sample_id: int) -> Sample:
    sample = db.get(Sample, sample_id)
    if not sample or sample.deleted_at:
        raise ApiError("SAMPLE_NOT_FOUND", "台账记录不存在", 404)
    return sample


@router.post("")
def post_sample(
    payload: SampleCreate,
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=160),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sample, created = create_sample(db, payload, user, idempotency_key, request.app.state.settings.app_timezone)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return serialize_sample(db, sample, request.app.state.settings.app_timezone)


@router.get("")
def get_samples(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    meal: str | None = None,
    keyword: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = list_samples(db, request.app.state.settings.app_timezone, status_filter, meal, keyword)
    return {"items": items, "total": len(items)}


@router.get("/{sample_id}")
def get_sample(
    sample_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return serialize_sample(db, require_sample(db, sample_id), request.app.state.settings.app_timezone, True)


@router.post("/{sample_id}/dispose")
def post_disposal(
    sample_id: int,
    payload: DisposalCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sample = dispose_sample(db, require_sample(db, sample_id), user, payload, request.app.state.settings.app_timezone)
    return serialize_sample(db, sample, request.app.state.settings.app_timezone, True)


@router.delete("/{sample_id}")
def delete_sample(
    sample_id: int,
    request: Request,
    reason: str = Query(min_length=1, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sample = soft_delete_sample(
        db,
        require_sample(db, sample_id),
        user,
        reason,
        request.app.state.settings.app_timezone,
    )
    return {"id": sample.id, "status": "deleted"}

