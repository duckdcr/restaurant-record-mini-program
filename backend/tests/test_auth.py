from fastapi.testclient import TestClient


def test_dev_login_persists_one_user(client, app):
    from backend.app.models import User

    response = client.post("/api/v1/auth/dev", json={"display_name": "王丽"})

    assert response.status_code == 200
    assert response.json()["user"]["display_name"] == "王丽"
    with app.state.SessionLocal() as session:
        assert session.query(User).count() == 1


def test_repeated_dev_login_reuses_user(client, app):
    from backend.app.models import User

    first = client.post("/api/v1/auth/dev", json={"display_name": "王丽"})
    second = client.post("/api/v1/auth/dev", json={"display_name": "王丽"})

    assert first.status_code == second.status_code == 200
    with app.state.SessionLocal() as session:
        assert session.query(User).count() == 1


def test_authenticated_me_returns_the_token_user(client):
    login = client.post("/api/v1/auth/dev", json={"display_name": "王丽"}).json()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "王丽"


def test_production_rejects_dev_login(tmp_path):
    from backend.app.config import Settings
    from backend.app.main import create_app

    settings = Settings(
        app_env="production",
        database_url=f"sqlite:///{(tmp_path / 'prod.db').as_posix()}",
        session_secret="production-session-secret-that-is-long-enough",
        wechat_app_id="wx-test",
        wechat_app_secret="secret",
        storage_local_dir=str(tmp_path / "uploads"),
        reports_dir=str(tmp_path / "reports"),
    )
    with TestClient(create_app(settings)) as production_client:
        response = production_client.post("/api/v1/auth/dev", json={"display_name": "王丽"})

    assert response.status_code == 404


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer broken-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_SESSION"

