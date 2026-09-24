from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256

from .config import Settings
from .database import Base, make_engine, make_session_factory
from .models import (
    AuditEvent,
    Menu,
    MenuItem,
    Sample,
    SampleImage,
    User,
    Upload,
)
from .services.menus import save_menu, latest_menu
from .storage import storage_for


SEED_IMAGE = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\x0DIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
)
SEED_DISHES = {
    "breakfast": ["南瓜粥", "鸡蛋羹", "豆浆"],
    "lunch": ["清炒时蔬", "番茄炒蛋", "米饭"],
    "dinner": ["红烧肉", "凉拌黄瓜", "豆腐脑"],
    "snack": ["水果拼盘"],
}


def ensure_menus(db, target_date: date, actor: User):
    for meal, items in SEED_DISHES.items():
        latest = latest_menu(db, target_date, meal)
        if not latest:
            save_menu(db, target_date, meal, items, actor)


def ensure_user(db) -> User:
    user = db.query(User).filter_by(openid="seed:demo").one_or_none()
    if user:
        return user
    user = User(openid="seed:demo", display_name="演示管理员", avatar_url="")
    db.add(user)
    db.flush()
    db.add(
        AuditEvent(
            entity_type="user",
            entity_id=user.id,
            action="created",
            actor_id=user.id,
            after_json='{"openid":"seed:demo","display_name":"演示管理员"}',
        )
    )
    db.flush()
    return user


def ensure_upload_and_sample(db, actor: User, target_date: date, settings) -> None:
    sample = db.query(Sample).filter_by(dish_name="清炒时蔬").one_or_none()
    if sample and sample.images:
        return

    storage = storage_for(settings)
    upload_key = None
    sha = sha256(SEED_IMAGE).hexdigest()
    if not db.query(Upload).filter_by(sha256=sha).one_or_none():
        upload_key = storage.save(SEED_IMAGE, ".png")
        db.add(
            Upload(
                owner_id=actor.id,
                storage_key=upload_key,
                sha256=sha,
                mime_type="image/png",
                size_bytes=len(SEED_IMAGE),
                original_name="seed.png",
            )
        )
        db.flush()

    upload = db.query(Upload).filter_by(sha256=sha).one_or_none()
    if not upload:
        return

    existed = (
        db.query(Sample)
        .filter_by(dish_name="清炒时蔬", keeper_id=actor.id)
        .order_by(Sample.id.desc())
        .first()
    )
    if existed:
        return

    sampled_at = datetime.combine(target_date, datetime.min.time()) - timedelta(hours=49)
    lunch = latest_menu(db, target_date, "lunch")
    menu_item = lunch.items[0] if lunch and lunch.items else None

    sample = Sample(
        menu_item_id=menu_item.id if menu_item else None,
        dish_name="清炒时蔬",
        meal="lunch",
        sampled_at=sampled_at,
        expires_at=sampled_at + timedelta(hours=48),
        keeper_id=actor.id,
        amount_g=125.0,
        temperature_c=4.0,
        note="演示数据：已过期样本，可直接演示处置流程",
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
    db.add(
        AuditEvent(
            entity_type="sample",
            entity_id=sample.id,
            action="seeded",
            actor_id=actor.id,
            after_json=f'{{"dish_name":"{sample.dish_name}","sampled_at":"{sampled_at.isoformat()}"}}',
        )
    )


def seed_database(settings: Settings | None = None) -> None:
    active_settings = settings or Settings()
    engine = make_engine(active_settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    target_date = datetime.now().date()
    with SessionLocal() as db:
        actor = ensure_user(db)
        ensure_menus(db, target_date, actor)
        ensure_upload_and_sample(db, actor, target_date, active_settings)
        db.commit()


def main():
    seed_database()


if __name__ == "__main__":
    main()
