import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .models import User


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int, retryable: bool = False, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


def create_access_token(user_id: int, settings: Settings) -> str:
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        user_id, issued_at, signature = decoded.split(":", 2)
        payload = f"{user_id}:{issued_at}"
        expected = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        if int(time.time()) - int(issued_at) > settings.session_ttl_seconds:
            raise ValueError("expired")
        return int(user_id)
    except (ValueError, UnicodeError, base64.binascii.Error):
        raise ApiError("INVALID_SESSION", "登录状态已失效，请重新登录", 401)


def get_db(request: Request):
    session = request.app.state.SessionLocal()
    try:
        yield session
    finally:
        session.close()


security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise ApiError("AUTH_REQUIRED", "请先登录", 401)
    user_id = decode_access_token(credentials.credentials, request.app.state.settings)
    user = db.get(User, user_id)
    if not user:
        raise ApiError("INVALID_SESSION", "登录状态已失效，请重新登录", 401)
    return user


async def exchange_wechat_code(code: str, settings: Settings) -> str:
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise ApiError("WECHAT_NOT_CONFIGURED", "微信登录尚未配置", 503)
    params = {
        "appid": settings.wechat_app_id,
        "secret": settings.wechat_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.weixin.qq.com/sns/jscode2session", params=params)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise ApiError("WECHAT_UNAVAILABLE", "微信登录服务暂时不可用", 502, True)
    if not data.get("openid"):
        raise ApiError("WECHAT_LOGIN_FAILED", "微信登录失败，请重试", 401)
    return data["openid"]


def upsert_user(db: Session, openid: str, display_name: str, avatar_url: str = "") -> User:
    user = db.query(User).filter(User.openid == openid).one_or_none()
    if not user:
        user = User(openid=openid, display_name=display_name, avatar_url=avatar_url)
        db.add(user)
    else:
        user.display_name = display_name or user.display_name
        user.avatar_url = avatar_url or user.avatar_url
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(user)
    return user
