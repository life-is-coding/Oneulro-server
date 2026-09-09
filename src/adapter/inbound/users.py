from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.core.dependencies import get_current_user
from src.adapter.outbound.notification_setting_repo import get_notification_settings, update_notification_settings
from src.adapter.outbound.user_repo import get_user, update_user
from src.application.session import update_redis_session
from src.core.config import get_settings

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None


class UpdateNotificationSettingsRequest(BaseModel):
    travel: Optional[bool] = None
    train: Optional[bool] = None
    community: Optional[bool] = None


@router.get("/me")
def profile_me(user=Depends(get_current_user)):
    """내 프로필 조회"""
    data = get_user(int(user["sub"]))
    if not data:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return data


@router.patch("/me")
def update_profile(body: UpdateProfileRequest, request: Request, user=Depends(get_current_user)):
    """프로필 수정 (닉네임, 프로필 이미지)"""
    updated = update_user(int(user["sub"]), body.nickname, body.profile_image_url)
    session_id = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    update_redis_session(session_id, {
        "nickname": updated.get("nickname"),
        "profile_image_url": updated.get("profile_image_url"),
    })
    return updated


@router.get("/me/notification-settings")
def my_notification_settings(user=Depends(get_current_user)):
    """내 알림 설정 조회"""
    return get_notification_settings(int(user["sub"]))


@router.put("/me/notification-settings")
def update_my_notification_settings(body: UpdateNotificationSettingsRequest, user=Depends(get_current_user)):
    """내 알림 설정 저장"""
    updates = {key: value for key, value in body.model_dump().items() if value is not None}
    return update_notification_settings(int(user["sub"]), updates)
