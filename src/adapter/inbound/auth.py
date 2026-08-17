from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from src.core.dependencies import get_current_user
from src.adapter.outbound.kakao_auth import exchange_code_for_token, fetch_kakao_profile
from src.application.session import create_session_token
from src.adapter.outbound.user_repo import upsert_user, clear_refresh_token, soft_delete_user

router = APIRouter(prefix="/auth", tags=["auth"])


class KakaoCallbackRequest(BaseModel):
    code: str


@router.post("/kakao/callback")
async def kakao_callback(body: KakaoCallbackRequest):
    """카카오 인가 코드를 받아 로그인 세션 토큰을 발급"""
    token_response = await exchange_code_for_token(body.code)
    profile = await fetch_kakao_profile(token_response["access_token"])

    user = upsert_user(
        kakao_id=profile["kakao_id"],
        nickname=profile["nickname"],
        profile_image_url=profile["profile_image_url"],
        refresh_token=token_response.get("refresh_token"),
    )

    session_token = create_session_token(user)

    return {
        "access_token": session_token,
        "user": {
            "id": user["user_id"],
            "nickname": user["nickname"],
            "profile_image_url": user["profile_image_url"],
        },
    }


@router.get("/me")
async def me(user=Depends(get_current_user)):
    """JWT 토큰 유효성 검증 및 사용자 정보 반환"""
    return {
        "id": user.get("sub"),
        "nickname": user.get("nickname"),
        "profile_image_url": user.get("profile_image_url"),
    }


@router.post("/logout")
async def logout(user=Depends(get_current_user)):
    """로그아웃 — DB의 refresh_token 삭제"""
    clear_refresh_token(int(user["sub"]))
    return {"message": "로그아웃 되었습니다"}


@router.delete("/me")
async def delete_me(user=Depends(get_current_user)):
    """회원탈퇴 — soft delete"""
    soft_delete_user(int(user["sub"]))
    return {"message": "회원탈퇴가 완료되었습니다"}
