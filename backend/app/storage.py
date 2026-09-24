from __future__ import annotations

import json
import uuid
from pathlib import Path
from xml.etree import ElementTree

try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:  # pragma: no cover - optional dependency for S3 deployments
    boto3 = None
    BotoConfig = None


def safe_s3_error_details(content: bytes) -> dict[str, object]:
    try:
        text = content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return {}
    if not text:
        return {}

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        allowed = ("code", "message", "error", "statusCode")
        return {key: payload[key] for key in allowed if key in payload}

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        # Provider-generated plain-text errors are safe to retain in a short,
        # bounded form. Never log the request, signed URL, or object contents.
        return {"message": text[:500]}

    details = {}
    for output_key, tag in (("code", "Code"), ("message", "Message")):
        element = root.find(f".//{tag}")
        if element is None:
            element = root.find(f".//{{*}}{tag}")
        if element is not None and element.text:
            details[output_key] = element.text
    return details


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        content: bytes,
        extension: str,
        prefix: str = "originals",
        content_type: str | None = None,
    ) -> str:
        day_dir = self.root / prefix
        day_dir.mkdir(parents=True, exist_ok=True)
        key = f"{prefix}/{uuid.uuid4().hex}{extension}"
        (self.root / key).write_bytes(content)
        return key

    def read(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in path.parents:
            raise FileNotFoundError(key)
        return path.read_bytes()


class S3Storage:
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
    ):
        if boto3 is None:
            raise RuntimeError("S3 storage requires optional dependency boto3")
        if not bucket:
            raise RuntimeError("S3 storage requires S3_BUCKET")
        if not access_key_id or not secret_access_key:
            raise RuntimeError("S3 storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY")
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name or "us-east-1",
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        events = getattr(getattr(self.client, "meta", None), "events", None)
        if events is not None:
            events.register("after-call.s3.PutObject", self._log_put_object_error)

    def _log_put_object_error(self, http_response, **_kwargs):
        if http_response.status_code < 400:
            return
        print(
            "Supabase S3 response",
            {
                **safe_s3_error_details(http_response.content),
                "content_type": http_response.headers.get("content-type"),
            },
        )

    def save(
        self,
        content: bytes,
        extension: str,
        prefix: str = "originals",
        content_type: str | None = None,
    ) -> str:
        key = f"{prefix}/{uuid.uuid4().hex}{extension}"
        request = {"Bucket": self.bucket, "Key": key, "Body": content}
        if content_type:
            request["ContentType"] = content_type
        try:
            self.client.put_object(**request)
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            error = response.get("Error", {}) or {}
            metadata = response.get("ResponseMetadata", {}) or {}
            # Keep the diagnostic limited to provider error metadata; never log
            # credentials, object contents, or signed request URLs.
            print(
                "S3 PutObject failed",
                {
                    "code": error.get("Code"),
                    "message": error.get("Message"),
                    "status": metadata.get("HTTPStatusCode"),
                },
            )
            raise
        return key

    def read(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # pragma: no cover - SDK dependent
            raise FileNotFoundError(key) from exc
        return response["Body"].read()


def storage_for(settings):
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_dir)
    if settings.storage_backend == "s3":
        return S3Storage(
            settings.s3_endpoint_url,
            settings.s3_bucket,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
            settings.s3_region,
        )
    raise RuntimeError("Unknown storage backend: " + settings.storage_backend)
