from datetime import date, datetime, timedelta

from backend.app.models import Menu, Sample, User


def test_effective_status_uses_four_and_forty_eight_hour_boundaries():
    from backend.app.services.dashboard import effective_status

    now = datetime(2026, 9, 10, 12, 0)
    assert effective_status(now - timedelta(hours=43, minutes=59), False, now) == "active"
    assert effective_status(now - timedelta(hours=44), False, now) == "warning"
    assert effective_status(now - timedelta(hours=48), False, now) == "expired"
    assert effective_status(now - timedelta(hours=60), True, now) == "disposed"


def test_dashboard_derives_missing_and_expired_items(client, auth_headers, app):
    client.put(
        "/api/v1/menus/2026-09-10/lunch",
        json={"items": ["土豆烧牛肉", "清炒时蔬", "米饭"]},
        headers=auth_headers,
    )
    with app.state.SessionLocal() as db:
        menu = (
            db.query(Menu)
            .filter(Menu.menu_date == date(2026, 9, 10), Menu.meal == "lunch")
            .order_by(Menu.version.desc())
            .first()
        )
        user = db.query(User).first()
        sampled_at = datetime.now() - timedelta(hours=49)
        db.add(
            Sample(
                menu_item_id=menu.items[0].id,
                dish_name=menu.items[0].dish_name,
                meal="lunch",
                sampled_at=sampled_at,
                expires_at=sampled_at + timedelta(hours=48),
                keeper_id=user.id,
                amount_g=125,
                temperature_c=4,
            )
        )
        db.commit()

    response = client.get("/api/v1/dashboard?date=2026-09-10", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_count"] == 3
    assert data["summary"]["registered_count"] == 1
    assert data["summary"]["missing_count"] == 2
    assert data["summary"]["expired_count"] == 1
    assert len(data["tasks"]) <= 3
    assert data["tasks"][0]["type"] == "danger"


def test_dashboard_requires_authentication(client):
    response = client.get("/api/v1/dashboard?date=2026-09-10")

    assert response.status_code == 401
