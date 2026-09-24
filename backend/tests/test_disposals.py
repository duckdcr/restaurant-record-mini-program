from datetime import datetime, timedelta

from backend.tests.test_samples import sample_payload


def create_expired(client, auth_headers, uploaded_image, key, dish):
    sampled_at = datetime.now().replace(microsecond=0) - timedelta(hours=49)
    return client.post(
        "/api/v1/samples",
        json=sample_payload(uploaded_image["id"], sampled_at, dish),
        headers={**auth_headers, "Idempotency-Key": key},
    ).json()


def test_disposal_preserves_note_reviewer_and_other_expired_record(client, auth_headers, png_bytes):
    first_upload = client.post(
        "/api/v1/uploads", files={"file": ("a.png", png_bytes, "image/png")}, headers=auth_headers
    ).json()
    second_upload = client.post(
        "/api/v1/uploads", files={"file": ("b.png", png_bytes, "image/png")}, headers=auth_headers
    ).json()
    target = create_expired(client, auth_headers, first_upload, "expired-1", "茶叶蛋")
    untouched = create_expired(client, auth_headers, second_upload, "expired-2", "红烧豆腐")

    response = client.post(
        f"/api/v1/samples/{target['id']}/dispose",
        json={"method": "discard", "note": "外观无异常", "reviewer_name": "张海涛"},
        headers=auth_headers,
    )
    untouched_detail = client.get(f"/api/v1/samples/{untouched['id']}", headers=auth_headers).json()

    assert response.status_code == 200
    assert response.json()["disposal"]["reviewer_name"] == "张海涛"
    assert response.json()["disposal"]["note"] == "外观无异常"
    assert response.json()["status"] == "disposed"
    assert untouched_detail["status"] == "expired"


def test_active_sample_cannot_be_disposed(client, auth_headers, uploaded_image):
    created = client.post(
        "/api/v1/samples",
        json=sample_payload(uploaded_image["id"]),
        headers={**auth_headers, "Idempotency-Key": "active-sample"},
    ).json()

    response = client.post(
        f"/api/v1/samples/{created['id']}/dispose",
        json={"method": "discard", "note": "", "reviewer_name": "张海涛"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "SAMPLE_NOT_DISPOSABLE"
