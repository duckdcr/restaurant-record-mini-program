from datetime import datetime, timedelta
from io import BytesIO

from openpyxl import load_workbook

from backend.tests.test_samples import sample_payload


def test_menu_to_sample_to_disposal_to_report(client, auth_headers, uploaded_image):
    client.put(
        "/api/v1/menus/2026-09-10/lunch",
        json={"items": ["清炒时蔬", "番茄炒蛋", "米饭"]},
        headers=auth_headers,
    )

    sampled_at = datetime.now().replace(microsecond=0) - timedelta(hours=50)
    payload = sample_payload(uploaded_image["id"], sampled_at, "清炒时蔬")
    created = client.post(
        "/api/v1/samples",
        json=payload,
        headers={**auth_headers, "Idempotency-Key": "e2e-main-flow"},
    )
    assert created.status_code == 201
    sample = created.json()

    detail = client.get(f"/api/v1/samples/{sample['id']}", headers=auth_headers)
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["audit_events"][0]["action"] == "created"

    disposed = client.post(
        f"/api/v1/samples/{sample['id']}/dispose",
        json={"method": "discard", "note": "到期废弃", "reviewer_name": "王丽"},
        headers=auth_headers,
    )
    assert disposed.status_code == 200
    assert disposed.json()["disposal"]["reviewer_name"] == "王丽"

    report = client.post(
        "/api/v1/reports",
        json={
            "date_from": sampled_at.date().isoformat(),
            "date_to": datetime.now().date().isoformat(),
        },
        headers=auth_headers,
    )
    assert report.status_code == 201

    download = client.get(report.json()["download_url"], headers=auth_headers)
    assert download.status_code == 200
    workbook = load_workbook(BytesIO(download.content))
    assert workbook.active["A2"].value == "清炒时蔬"
    assert workbook.active["K2"].value == "王丽"
