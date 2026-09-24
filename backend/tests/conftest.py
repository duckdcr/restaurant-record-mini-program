import os
import sys
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def settings(tmp_path: Path):
    from backend.app.config import Settings

    return Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        session_secret="test-session-secret-that-is-long-enough",
        storage_local_dir=str(tmp_path / "uploads"),
        reports_dir=str(tmp_path / "reports"),
    )


@pytest.fixture()
def app(settings):
    from backend.app.main import create_app

    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client):
    response = client.post("/api/v1/auth/dev", json={"display_name": "王丽"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def png_bytes():
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


@pytest.fixture()
def uploaded_image(client, auth_headers, png_bytes):
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("label.png", png_bytes, "image/png")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()
