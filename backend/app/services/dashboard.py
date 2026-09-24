from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..models import Sample
from .menus import MEALS, MEAL_LABELS, get_menu_for_date, latest_menu


def effective_status(sampled_at: datetime, disposed: bool, now: datetime) -> str:
    if disposed:
        return "disposed"
    remaining = sampled_at + timedelta(hours=48) - now
    if remaining.total_seconds() <= 0:
        return "expired"
    if remaining <= timedelta(hours=4):
        return "warning"
    return "active"


def current_local_time(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name)).replace(tzinfo=None)


def build_dashboard(db: Session, target_date: date, timezone_name: str) -> dict:
    now = current_local_time(timezone_name)
    menu_data = get_menu_for_date(db, target_date)
    latest_items = {}
    for meal in MEALS:
        menu = latest_menu(db, target_date, meal)
        if menu:
            latest_items[meal] = menu.items

    active_samples = db.query(Sample).filter(Sample.deleted_at.is_(None)).all()
    sample_status = {
        sample.id: effective_status(sample.sampled_at, sample.disposal is not None, now)
        for sample in active_samples
    }
    current_item_ids = {item.id for items in latest_items.values() for item in items}
    registered_item_ids = {
        sample.menu_item_id for sample in active_samples if sample.menu_item_id in current_item_ids
    }
    total_count = len(current_item_ids)
    registered_count = len(registered_item_ids)
    missing_count = max(0, total_count - registered_count)
    warning_count = sum(1 for value in sample_status.values() if value == "warning")
    expired_count = sum(1 for value in sample_status.values() if value == "expired")

    tasks = []
    for sample in active_samples:
        status = sample_status[sample.id]
        if status not in {"expired", "warning"}:
            continue
        remaining = sample.expires_at - now
        if status == "expired":
            hours = abs(remaining.total_seconds()) / 3600
            tasks.append(
                {
                    "id": f"sample-{sample.id}",
                    "type": "danger",
                    "title": f"{sample.dish_name}已超过 48 小时",
                    "sub": f"{MEAL_LABELS.get(sample.meal, sample.meal)} · {sample.sampled_at:%m月%d日 %H:%M}",
                    "time": f"+{hours:.1f}h",
                    "action": "dispose",
                    "record_id": sample.id,
                }
            )
        else:
            tasks.append(
                {
                    "id": f"sample-{sample.id}",
                    "type": "warning",
                    "title": f"{sample.dish_name}将在 4 小时内到期",
                    "sub": f"{MEAL_LABELS.get(sample.meal, sample.meal)} · {sample.expires_at:%m月%d日 %H:%M}",
                    "time": sample.expires_at.strftime("%H:%M"),
                    "action": "ledger-warning",
                    "record_id": sample.id,
                }
            )

    meals = []
    for meal in MEALS[:3]:
        items = latest_items.get(meal, [])
        done = sum(1 for item in items if item.id in registered_item_ids)
        total = len(items)
        missing_names = [item.dish_name for item in items if item.id not in registered_item_ids]
        meals.append(
            {
                "key": meal,
                "name": MEAL_LABELS[meal],
                "registered": done,
                "total": total,
                "missing": missing_names,
                "percent": round(done / total * 100) if total else 0,
            }
        )
        if missing_names:
            tasks.append(
                {
                    "id": f"missing-{meal}",
                    "type": "warning",
                    "title": f"{MEAL_LABELS[meal]}还有 {len(missing_names)} 道未留样",
                    "sub": "、".join(missing_names),
                    "time": f"缺 {len(missing_names)}",
                    "action": "scan",
                    "meal": meal,
                }
            )

    priority = {"danger": 0, "warning": 1}
    tasks.sort(key=lambda item: (priority[item["type"]], 0 if item["action"] != "scan" else 1))
    return {
        "date": target_date.isoformat(),
        "summary": {
            "total_count": total_count,
            "registered_count": registered_count,
            "missing_count": missing_count,
            "warning_count": warning_count,
            "expired_count": expired_count,
        },
        "tasks": tasks[:3],
        "meals": meals,
        "menus": menu_data["meals"],
        "generated_at": now.isoformat(),
    }

