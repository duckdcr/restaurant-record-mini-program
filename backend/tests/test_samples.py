from datetime import datetime, timedelta

from backend.app.models import AuditEvent, IdempotencyKey, Sample, SampleImage


def sample_payload(upload_id, sampled_at=None, dish_name="清炒时蔬"):
    sampled_at = sampled_at or datetime.now().replace(microsecond=0)
    return {
        "menu_item_id": None,
        "dish_name": dish_name,
        "meal": "lunch",
        "sampled_at": sampled_at.isoformat(),
        "amount_g": 125,
        "temperature_c": 4,
        "note": "标签完整",
        "upload_id": upload_id,
        "recognition_run_id": None,
        "fields": {
            "dish_name": {"raw_value": dish_name, "source": "manual", "confidence": None},
            "meal": {"raw_value": "lunch", "source": "manual", "confidence": None},
            "sampled_at": {"raw_value": sampled_at.isoformat(), "source": "manual", "confidence": None},
            "amount_g": {"raw_value": "125", "source": "default", "confidence": 0},
            "temperature_c": {"raw_value": "4", "source": "default", "confidence": 0},
        },
        "confirmed_fields": ["amount_g", "temperature_c"],
    }


def test_sample_creation_is_idempotent_and_persists_evidence(client, auth_headers, uploaded_image, app):
    payload = sample_payload(uploaded_image["id"])
    headers = {**auth_headers, "Idempotency-Key": "device-1-entry-1"}

    first = client.post("/api/v1/samples", json=payload, headers=headers)
    second = client.post("/api/v1/samples", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["expires_at"] == (datetime.fromisoformat(payload["sampled_at"]) + timedelta(hours=48)).isoformat()
    with app.state.SessionLocal() as db:
        assert db.query(Sample).count() == 1
        assert db.query(SampleImage).count() == 1
        assert db.query(IdempotencyKey).count() == 1
        assert db.query(AuditEvent).filter(AuditEvent.action == "created").count() == 1


def test_default_amount_and_temperature_require_confirmation(client, auth_headers, uploaded_image):
    payload = sample_payload(uploaded_image["id"])
    payload["confirmed_fields"] = []

    response = client.post(
        "/api/v1/samples",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": "missing-confirmation"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "CONFIRMATION_REQUIRED"


def test_sample_detail_returns_real_audit_and_image_hash(client, auth_headers, uploaded_image):
    created = client.post(
        "/api/v1/samples",
        json=sample_payload(uploaded_image["id"]),
        headers={**auth_headers, "Idempotency-Key": "detail-sample"},
    ).json()

    response = client.get(f"/api/v1/samples/{created['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["images"][0]["sha256"] == uploaded_image["sha256"]
    assert response.json()["audit_events"][0]["action"] == "created"
    assert response.json()["fields"]["amount_g"]["source"] == "default"


def test_soft_delete_requires_reason_and_hides_record(client, auth_headers, uploaded_image):
    created = client.post(
        "/api/v1/samples",
        json=sample_payload(uploaded_image["id"]),
        headers={**auth_headers, "Idempotency-Key": "delete-sample"},
    ).json()

    missing_reason = client.delete(f"/api/v1/samples/{created['id']}", headers=auth_headers)
    deleted = client.delete(f"/api/v1/samples/{created['id']}?reason=标签录入错误", headers=auth_headers)
    records = client.get("/api/v1/samples", headers=auth_headers).json()

    assert missing_reason.status_code == 422
    assert deleted.status_code == 200
    assert records["items"] == []

