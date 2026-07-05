from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.repositories.user_repo import get_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None


@router.get("/me")
def profile_me(user=Depends(get_current_user)):
    """내 프로필 조회"""
    data = get_user(int(user["sub"]))
    if not data:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return data


@router.patch("/me")
def update_profile(body: UpdateProfileRequest, user=Depends(get_current_user)):
    """프로필 수정 (닉네임, 프로필 이미지)"""
    return update_user(int(user["sub"]), body.nickname, body.profile_image_url)
