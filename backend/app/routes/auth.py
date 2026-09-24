from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import create_access_token, exchange_wechat_code, get_current_user, get_db, upsert_user
from ..models import User
from ..schemas import DevLoginRequest, LoginResponse, UserResponse, WechatLoginRequest


router = APIRouter(prefix="/auth", tags=["auth"])


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, display_name=user.display_name, avatar_url=user.avatar_url)


@router.post("/dev", response_model=LoginResponse)
def dev_login(payload: DevLoginRequest, request: Request, db: Session = Depends(get_db)):
    if request.app.state.settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Development login is disabled in production.")
    user = upsert_user(db, f"dev:{payload.display_name}", payload.display_name)
    return LoginResponse(
        access_token=create_access_token(user.id, request.app.state.settings),
        user=user_response(user),
    )


@router.post("/wechat", response_model=LoginResponse)
async def wechat_login(payload: WechatLoginRequest, request: Request, db: Session = Depends(get_db)):
    openid = await exchange_wechat_code(payload.code, request.app.state.settings)
    user = upsert_user(db, openid, payload.display_name, payload.avatar_url)
    return LoginResponse(
        access_token=create_access_token(user.id, request.app.state.settings),
        user=user_response(user),
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user_response(user)
