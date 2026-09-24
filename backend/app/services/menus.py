from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..auth import ApiError
from ..models import AuditEvent, Menu, MenuItem, User


MEALS = ("breakfast", "lunch", "dinner", "snack")
MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}


def normalize_dish(name: str) -> str:
    return "".join((name or "").strip().casefold().split())


def validate_items(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    normalized = [normalize_dish(item) for item in cleaned]
    if not cleaned:
        raise ApiError("MENU_EMPTY", "菜单至少需要一道菜", 422)
    if len(set(normalized)) != len(normalized):
        raise ApiError("MENU_DUPLICATE", "菜单中存在重复菜名", 422)
    if len(cleaned) > 100:
        raise ApiError("MENU_TOO_LARGE", "单个餐次最多100道菜", 422)
    return cleaned


def latest_menu(db: Session, menu_date: date, meal: str) -> Menu | None:
    return (
        db.query(Menu)
        .options(selectinload(Menu.items))
        .filter(Menu.menu_date == menu_date, Menu.meal == meal)
        .order_by(Menu.version.desc())
        .first()
    )


def serialize_menu(menu: Menu) -> dict:
    return {
        "id": menu.id,
        "date": menu.menu_date.isoformat(),
        "meal": menu.meal,
        "meal_label": MEAL_LABELS[menu.meal],
        "version": menu.version,
        "items": [
            {"id": item.id, "dish_name": item.dish_name, "sort_order": item.sort_order}
            for item in menu.items
        ],
    }


def save_menu(db: Session, menu_date: date, meal: str, items: list[str], actor: User) -> Menu:
    cleaned = validate_items(items)
    version = (
        db.query(func.max(Menu.version))
        .filter(Menu.menu_date == menu_date, Menu.meal == meal)
        .scalar()
        or 0
    ) + 1
    menu = Menu(menu_date=menu_date, meal=meal, version=version, created_by=actor.id)
    menu.items = [
        MenuItem(dish_name=name, normalized_name=normalize_dish(name), sort_order=index)
        for index, name in enumerate(cleaned)
    ]
    db.add(menu)
    db.flush()
    db.add(
        AuditEvent(
            entity_type="menu",
            entity_id=menu.id,
            action="created",
            actor_id=actor.id,
            after_json=str({"date": menu_date.isoformat(), "meal": meal, "version": version, "items": cleaned}),
        )
    )
    db.commit()
    db.refresh(menu)
    return latest_menu(db, menu_date, meal)


def get_menu_for_date(db: Session, menu_date: date) -> dict:
    meals = {}
    for meal in MEALS:
        menu = latest_menu(db, menu_date, meal)
        if menu:
            meals[meal] = serialize_menu(menu)
    return {"date": menu_date.isoformat(), "meals": meals}


def copy_previous_menu(db: Session, target_date: date, actor: User) -> dict:
    previous_dates = [
        value[0]
        for value in db.query(Menu.menu_date)
        .filter(Menu.menu_date < target_date)
        .distinct()
        .order_by(Menu.menu_date.desc())
        .all()
    ]
    if not previous_dates:
        raise ApiError("NO_PREVIOUS_MENU", "没有可复制的历史菜单", 404)
    source_date = previous_dates[0]
    for meal in MEALS:
        source = latest_menu(db, source_date, meal)
        if source:
            save_menu(db, target_date, meal, [item.dish_name for item in source.items], actor)
    return get_menu_for_date(db, target_date)

