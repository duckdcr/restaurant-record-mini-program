from pathlib import Path

from backend.app.models import Upload


def test_safe_s3_error_details_only_keeps_diagnostic_fields():
    from backend.app.storage import safe_s3_error_details

    details = safe_s3_error_details(
        b'{"code":"InvalidRequest","message":"bad request",'
        b'"error":"invalid_request","statusCode":"400",'
        b'"authorization":"must-not-be-logged"}'
    )

    assert details == {
        "code": "InvalidRequest",
        "message": "bad request",
        "error": "invalid_request",
        "statusCode": "400",
    }


def test_safe_s3_error_details_reads_xml_error():
    from backend.app.storage import safe_s3_error_details

    details = safe_s3_error_details(
        b"<Error><Code>InvalidRequest</Code><Message>bad request</Message>"
        b"<RequestId>private-request-id</RequestId></Error>"
    )

    assert details == {"code": "InvalidRequest", "message": "bad request"}


def test_safe_s3_error_details_reads_namespaced_s3_xml_error():
    from backend.app.storage import safe_s3_error_details

    details = safe_s3_error_details(
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Error xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        b"<Resource>sample-images/example.jpg</Resource>"
        b"<Code>InvalidAccessKeyId</Code>"
        b"<Message>The Access Key Id is invalid.</Message></Error>"
    )

    assert details == {
        "code": "InvalidAccessKeyId",
        "message": "The Access Key Id is invalid.",
    }


def test_safe_s3_error_details_reads_plain_text_without_dumping_large_body():
    from backend.app.storage import safe_s3_error_details

    details = safe_s3_error_details(b"Bad Request" + b"x" * 1000)

    assert details == {"message": ("Bad Request" + "x" * 489)}


def test_upload_saves_hash_and_file(client, auth_headers, png_bytes, app):
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("label.png", png_bytes, "image/png")},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["sha256"]) == 64
    assert data["mime_type"] == "image/png"
    with app.state.SessionLocal() as db:
        upload = db.get(Upload, data["id"])
        assert upload.size_bytes == len(png_bytes)
        assert Path(app.state.settings.storage_local_dir, upload.storage_key).exists()


def test_upload_rejects_non_image(client, auth_headers):
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("note.txt", b"not an image", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_IMAGE"


def test_upload_requires_authentication(client, png_bytes):
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("label.png", png_bytes, "image/png")},
    )

    assert response.status_code == 401


def test_s3_storage_uses_path_style_for_supabase(monkeypatch):
    import backend.app.storage as storage_module

    class FakeClient:
        pass

    class FakeBoto:
        def __init__(self):
            self.kwargs = None

        def client(self, *_args, **kwargs):
            self.kwargs = kwargs
            return FakeClient()

    fake_boto = FakeBoto()
    monkeypatch.setattr(storage_module, "boto3", fake_boto)

    storage_module.S3Storage("https://storage.example/s3", "bucket", "access", "secret", "region")

    config = fake_boto.kwargs["config"]
    assert config.s3["addressing_style"] == "path"
    assert config.signature_version == "s3v4"
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"


def test_s3_storage_sends_content_type_for_bucket_mime_restrictions(monkeypatch):
    import backend.app.storage as storage_module

    class FakeClient:
        def __init__(self):
            self.put_kwargs = None

        def put_object(self, **kwargs):
            self.put_kwargs = kwargs

    class FakeBoto:
        def __init__(self):
            self.client_instance = FakeClient()

        def client(self, *_args, **kwargs):
            return self.client_instance

    fake_boto = FakeBoto()
    monkeypatch.setattr(storage_module, "boto3", fake_boto)

    storage = storage_module.S3Storage(
        "https://storage.example/s3", "bucket", "access", "secret", "region"
    )
    storage.save(b"image", ".png", content_type="image/png")

    assert fake_boto.client_instance.put_kwargs["ContentType"] == "image/png"
