from datetime import date

from backend.app.models import Menu


def test_saving_menu_creates_new_version(client, auth_headers, app):
    body = {"items": ["土豆烧牛肉", "清炒时蔬", "米饭"]}

    first = client.put("/api/v1/menus/2026-09-10/lunch", json=body, headers=auth_headers)
    second = client.put("/api/v1/menus/2026-09-10/lunch", json=body, headers=auth_headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert second.json()["items"][1]["dish_name"] == "清炒时蔬"
    with app.state.SessionLocal() as db:
        assert db.query(Menu).filter(Menu.menu_date == date(2026, 9, 10)).count() == 2


def test_menu_rejects_empty_or_duplicate_dishes(client, auth_headers):
    empty = client.put(
        "/api/v1/menus/2026-09-10/lunch",
        json={"items": []},
        headers=auth_headers,
    )
    duplicate = client.put(
        "/api/v1/menus/2026-09-10/lunch",
        json={"items": ["米饭", " 米饭 "]},
        headers=auth_headers,
    )

    assert empty.status_code == 422
    assert duplicate.status_code == 422


def test_copy_previous_uses_latest_earlier_menu(client, auth_headers):
    client.put(
        "/api/v1/menus/2026-09-09/breakfast",
        json={"items": ["南瓜粥", "煮鸡蛋"]},
        headers=auth_headers,
    )

    response = client.post(
        "/api/v1/menus/2026-09-10/copy-previous",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["meals"]["breakfast"]["items"][0]["dish_name"] == "南瓜粥"

