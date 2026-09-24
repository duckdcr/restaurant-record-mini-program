import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class Settings(BaseModel):
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./backend/data/a2.db"
    session_secret: str = "development-only-change-me"
    session_ttl_seconds: int = 7 * 24 * 3600
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = 30.0
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: str = "./backend/data/uploads"
    reports_dir: str = "./backend/data/reports"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "us-east-1"
    cors_origins: list[str] = ["http://localhost"]
    app_timezone: str = "Asia/Shanghai"

    def _to_tmp_relative_path(self, raw_path: str) -> str:
        normalized = str(raw_path).replace("\\", "/").replace("./", "", 1)
        if normalized.startswith("backend/"):
            normalized = normalized[len("backend/") :]
        return str(Path("/tmp") / normalized)

    def _writable_path(self, raw_path: str) -> Path:
        target = Path(raw_path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            fallback = Path("/tmp") / str(raw_path).replace("\\", "/").replace("./", "").replace("backend/", "")
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return fallback

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def validate_production(self):
        if self.app_env == "production":
            missing = []
            if len(self.session_secret) < 24:
                missing.append("SESSION_SECRET")
            if not self.wechat_app_id:
                missing.append("WECHAT_APP_ID")
            if not self.wechat_app_secret:
                missing.append("WECHAT_APP_SECRET")
            if missing:
                raise ValueError("Production configuration missing: " + ", ".join(missing))
        return self

    @classmethod
    def from_env(cls):
        values = {}
        for name in cls.model_fields:
            key = name.upper()
            if key in os.environ:
                values[name] = os.environ[key]
        return cls(**values)

    def ensure_directories(self):
        if self.database_url.startswith("sqlite:///"):
            database_path = self.database_url[len("sqlite:///") :]
            if not Path(database_path).is_absolute():
                database_path = self._to_tmp_relative_path(database_path)
                self.database_url = "sqlite:///" + database_path
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        if self.storage_backend == "local":
            self.storage_local_dir = str(self._writable_path(self.storage_local_dir))
        self.reports_dir = str(self._writable_path(self.reports_dir))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
