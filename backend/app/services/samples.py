import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..auth import ApiError
from ..models import (
    AuditEvent,
    Disposal,
    IdempotencyKey,
    RecognitionField,
    RecognitionRun,
    Sample,
    SampleImage,
    Upload,
    User,
)
from .dashboard import current_local_time, effective_status
from .menus import MEAL_LABELS


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def append_audit(db: Session, entity_type: str, entity_id: int, action: str, actor_id: int, before, after):
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        before_json=json_text(before) if before is not None else "",
        after_json=json_text(after) if after is not None else "",
    )
    db.add(event)
    return event


def status_for(sample: Sample, now: datetime) -> str:
    if sample.deleted_at:
        return "deleted"
    return effective_status(sample.sampled_at, sample.disposal is not None, now)


def serialize_disposal(disposal: Disposal | None) -> dict | None:
    if not disposal:
        return None
    return {
        "id": disposal.id,
        "method": disposal.method,
        "note": disposal.note,
        "operator_id": disposal.operator_id,
        "reviewer_name": disposal.reviewer_name,
        "disposed_at": disposal.disposed_at.isoformat(),
    }


def serialize_sample(db: Session, sample: Sample, timezone_name: str, detail: bool = False) -> dict:
    now = current_local_time(timezone_name)
    keeper = db.get(User, sample.keeper_id)
    status = status_for(sample, now)
    result = {
        "id": sample.id,
        "menu_item_id": sample.menu_item_id,
        "dish_name": sample.dish_name,
        "meal": sample.meal,
        "meal_label": MEAL_LABELS.get(sample.meal, sample.meal),
        "sampled_at": sample.sampled_at.isoformat(),
        "expires_at": sample.expires_at.isoformat(),
        "keeper": {"id": keeper.id, "display_name": keeper.display_name},
        "amount_g": sample.amount_g,
        "temperature_c": sample.temperature_c,
        "note": sample.note,
        "status": status,
        "disposal": serialize_disposal(sample.disposal),
    }
    if detail:
        result["images"] = [
            {
                "id": image.id,
                "sha256": image.sha256,
                "mime_type": image.mime_type,
                "size_bytes": image.size_bytes,
            }
            for image in sample.images
        ]
        fields = db.query(RecognitionField).filter(RecognitionField.sample_id == sample.id).all()
        result["fields"] = {
            field.field_name: {
                "source": field.source,
                "raw_value": field.raw_value,
                "final_value": field.final_value,
                "confidence": field.confidence,
                "was_modified": field.was_modified,
            }
            for field in fields
        }
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.entity_type == "sample", AuditEvent.entity_id == sample.id)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            .all()
        )
        result["audit_events"] = [
            {
                "id": event.id,
                "action": event.action,
                "actor_id": event.actor_id,
                "before": json.loads(event.before_json) if event.before_json else None,
                "after": json.loads(event.after_json) if event.after_json else None,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
    return result


def create_sample(db: Session, payload, actor: User, idempotency_key: str, timezone_name: str) -> tuple[Sample, bool]:
    existing_key = (
        db.query(IdempotencyKey)
        .filter(IdempotencyKey.owner_id == actor.id, IdempotencyKey.key == idempotency_key)
        .one_or_none()
    )
    if existing_key:
        return db.get(Sample, existing_key.sample_id), False

    upload = db.get(Upload, payload.upload_id)
    if not upload or upload.owner_id != actor.id:
        raise ApiError("UPLOAD_NOT_FOUND", "图片不存在", 404)
    if db.query(SampleImage).filter(SampleImage.upload_id == upload.id).first():
        raise ApiError("UPLOAD_ALREADY_USED", "该图片已用于另一条台账", 409)
    if payload.recognition_run_id:
        run = db.get(RecognitionRun, payload.recognition_run_id)
        if not run or run.upload_id != upload.id or run.status != "succeeded":
            raise ApiError("RECOGNITION_NOT_FOUND", "识别记录无效", 422)

    required_confirmations = {
        name for name in ("amount_g", "temperature_c")
        if payload.fields.get(name) and payload.fields[name].source == "default"
    }
    if not required_confirmations.issubset(set(payload.confirmed_fields)):
        raise ApiError("CONFIRMATION_REQUIRED", "默认重量和温度必须人工确认", 422)

    sample = Sample(
        menu_item_id=payload.menu_item_id,
        dish_name=payload.dish_name.strip(),
        meal=payload.meal,
        sampled_at=payload.sampled_at.replace(tzinfo=None),
        expires_at=payload.sampled_at.replace(tzinfo=None) + timedelta(hours=48),
        keeper_id=actor.id,
        amount_g=payload.amount_g,
        temperature_c=payload.temperature_c,
        note=payload.note.strip(),
        status="active",
    )
    db.add(sample)
    db.flush()
    db.add(
        SampleImage(
            sample_id=sample.id,
            upload_id=upload.id,
            storage_key=upload.storage_key,
            sha256=upload.sha256,
            mime_type=upload.mime_type,
            size_bytes=upload.size_bytes,
        )
    )
    final_values = {
        "dish_name": sample.dish_name,
        "meal": sample.meal,
        "sampled_at": sample.sampled_at.isoformat(),
        "amount_g": str(sample.amount_g),
        "temperature_c": str(sample.temperature_c),
    }
    for name, evidence in payload.fields.items():
        final_value = final_values.get(name, evidence.raw_value)
        db.add(
            RecognitionField(
                sample_id=sample.id,
                run_id=payload.recognition_run_id,
                field_name=name,
                source=evidence.source,
                raw_value=str(evidence.raw_value or ""),
                final_value=str(final_value or ""),
                confidence=evidence.confidence,
                was_modified=str(evidence.raw_value or "") != str(final_value or ""),
            )
        )
    append_audit(
        db,
        "sample",
        sample.id,
        "created",
        actor.id,
        None,
        {
            "dish_name": sample.dish_name,
            "meal": sample.meal,
            "sampled_at": sample.sampled_at.isoformat(),
            "upload_sha256": upload.sha256,
            "confirmed_fields": payload.confirmed_fields,
        },
    )
    db.add(IdempotencyKey(owner_id=actor.id, key=idempotency_key, sample_id=sample.id))
    db.commit()
    db.refresh(sample)
    return sample, True


def list_samples(db: Session, timezone_name: str, status: str | None = None, meal: str | None = None, keyword: str = "") -> list[dict]:
    samples = db.query(Sample).filter(Sample.deleted_at.is_(None)).order_by(Sample.sampled_at.desc()).all()
    result = []
    query = keyword.strip().casefold()
    for sample in samples:
        item = serialize_sample(db, sample, timezone_name)
        if status and item["status"] != status:
            continue
        if meal and sample.meal != meal:
            continue
        if query and query not in f"{sample.dish_name} {item['keeper']['display_name']}".casefold():
            continue
        result.append(item)
    return result


def dispose_sample(db: Session, sample: Sample, actor: User, payload, timezone_name: str) -> Sample:
    now = current_local_time(timezone_name)
    current_status = status_for(sample, now)
    if current_status not in {"warning", "expired"}:
        raise ApiError("SAMPLE_NOT_DISPOSABLE", "该留样尚未到可处置状态", 409)
    if sample.disposal:
        raise ApiError("SAMPLE_ALREADY_DISPOSED", "该留样已经处置", 409)
    disposal = Disposal(
        sample_id=sample.id,
        method=payload.method,
        note=payload.note.strip(),
        operator_id=actor.id,
        reviewer_name=payload.reviewer_name.strip(),
        disposed_at=now,
    )
    db.add(disposal)
    sample.status = "disposed"
    append_audit(db, "sample", sample.id, "disposed", actor.id, {"status": current_status}, payload.model_dump())
    db.commit()
    db.refresh(sample)
    return sample


def soft_delete_sample(db: Session, sample: Sample, actor: User, reason: str, timezone_name: str) -> Sample:
    before = {"status": status_for(sample, current_local_time(timezone_name))}
    sample.deleted_at = current_local_time(timezone_name)
    sample.status = "deleted"
    append_audit(db, "sample", sample.id, "deleted", actor.id, before, {"reason": reason.strip()})
    db.commit()
    db.refresh(sample)
    return sample

