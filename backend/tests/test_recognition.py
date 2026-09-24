import json

from backend.app.models import RecognitionRun


def test_recognition_reports_not_configured_without_fake_result(client, auth_headers, uploaded_image, app):
    response = client.post(
        "/api/v1/recognitions",
        json={"upload_id": uploaded_image["id"], "meal": "lunch", "menu_date": "2026-09-10"},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert response.json()["code"] == "AI_NOT_CONFIGURED"
    with app.state.SessionLocal() as db:
        run = db.query(RecognitionRun).one()
        assert run.status == "failed"
        assert run.error_code == "AI_NOT_CONFIGURED"
        assert run.structured_result_json == ""


def test_recognition_parses_field_sources_and_defaults(monkeypatch, client, auth_headers, uploaded_image, app):
    from backend.app.services.recognition import RecognitionService

    menu = client.put(
        "/api/v1/menus/2026-09-10/lunch",
        json={"items": ["清炒时蔬", "米饭"]},
        headers=auth_headers,
    )
    assert menu.status_code == 200
    app.state.settings.ai_base_url = "https://ai.example.test/v1"
    app.state.settings.ai_api_key = "test-key"
    app.state.settings.ai_model = "vision-test"

    async def fake_call(self, image_bytes, mime_type, menu_candidates):
        return {
            "dish_name": {"value": "清炒时蔬", "confidence": 0.61},
            "meal": {"value": "lunch", "confidence": 0.98},
            "sampled_at": {"value": "2026-09-10T10:48:00", "confidence": 0.96},
            "keeper": {"value": "王丽", "confidence": 0.93},
            "amount_g": {"value": None, "confidence": 0},
            "temperature_c": {"value": None, "confidence": 0},
        }

    monkeypatch.setattr(RecognitionService, "_call_upstream", fake_call)
    response = client.post(
        "/api/v1/recognitions",
        json={"upload_id": uploaded_image["id"], "meal": "lunch", "menu_date": "2026-09-10"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    fields = response.json()["fields"]
    assert fields["dish_name"]["source"] == "menu_match"
    assert fields["dish_name"]["requires_confirmation"] is True
    assert fields["amount_g"] == {
        "value": 125.0,
        "confidence": 0.0,
        "source": "default",
        "requires_confirmation": True,
    }
    with app.state.SessionLocal() as db:
        run = db.query(RecognitionRun).one()
        assert json.loads(run.structured_result_json)["temperature_c"]["source"] == "default"


def test_user_cannot_recognize_another_users_upload(client, uploaded_image):
    other_login = client.post("/api/v1/auth/dev", json={"display_name": "张海涛"}).json()
    response = client.post(
        "/api/v1/recognitions",
        json={"upload_id": uploaded_image["id"], "meal": "lunch", "menu_date": "2026-09-10"},
        headers={"Authorization": f"Bearer {other_login['access_token']}"},
    )

    assert response.status_code == 404
