from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Menu(Base):
    __tablename__ = "menus"
    __table_args__ = (UniqueConstraint("menu_date", "meal", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    menu_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    items: Mapped[list[MenuItem]] = relationship(cascade="all, delete-orphan", order_by="MenuItem.sort_order")


class MenuItem(Base):
    __tablename__ = "menu_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"), index=True)
    dish_name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecognitionRun(Base):
    __tablename__ = "recognition_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), default="openai-compatible")
    model: Mapped[str] = mapped_column(String(160), default="")
    model_version: Mapped[str] = mapped_column(String(160), default="")
    raw_response_json: Mapped[str] = mapped_column(Text, default="")
    structured_result_json: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), index=True)
    error_code: Mapped[str] = mapped_column(String(80), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Sample(Base):
    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(primary_key=True)
    menu_item_id: Mapped[int | None] = mapped_column(ForeignKey("menu_items.id"), nullable=True, index=True)
    dish_name: Mapped[str] = mapped_column(String(160), index=True)
    meal: Mapped[str] = mapped_column(String(20), index=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    keeper_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_g: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    images: Mapped[list[SampleImage]] = relationship(cascade="all, delete-orphan")
    disposal: Mapped[Disposal | None] = relationship(uselist=False, cascade="all, delete-orphan")


class SampleImage(Base):
    __tablename__ = "sample_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), unique=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)


class RecognitionField(Base):
    __tablename__ = "recognition_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("recognition_runs.id"), nullable=True)
    field_name: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(30))
    raw_value: Mapped[str] = mapped_column(Text, default="")
    final_value: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    was_modified: Mapped[bool] = mapped_column(Boolean, default=False)


class Disposal(Base):
    __tablename__ = "disposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"), unique=True, index=True)
    method: Mapped[str] = mapped_column(String(50))
    note: Mapped[str] = mapped_column(Text, default="")
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewer_name: Mapped[str] = mapped_column(String(80))
    disposed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    before_json: Mapped[str] = mapped_column(Text, default="")
    after_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(160))
    sample_id: Mapped[int] = mapped_column(ForeignKey("samples.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("owner_id", "key"),)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date_from: Mapped[datetime.date] = mapped_column(Date)
    date_to: Mapped[datetime.date] = mapped_column(Date)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
