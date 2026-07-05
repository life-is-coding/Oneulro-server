from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from src.services.kakao_auth import exchange_code_for_token, fetch_kakao_profile
from src.services.session import create_session_token, decode_session_token
from src.repositories.user_repo import upsert_user, clear_refresh_token, soft_delete_user

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
async def me(authorization: Optional[str] = Header(None)):
    """JWT 토큰 유효성 검증 및 사용자 정보 반환"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_session_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    return {
        "id": payload.get("sub"),
        "nickname": payload.get("nickname"),
        "profile_image_url": payload.get("profile_image_url"),
    }


def _require_auth(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다")
    try:
        return decode_session_token(authorization.removeprefix("Bearer "))
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """로그아웃 — DB의 refresh_token 삭제"""
    payload = _require_auth(authorization)
    clear_refresh_token(int(payload["sub"]))
    return {"message": "로그아웃 되었습니다"}


@router.delete("/me")
async def delete_me(authorization: Optional[str] = Header(None)):
    """회원탈퇴 — soft delete"""
    payload = _require_auth(authorization)
    soft_delete_user(int(payload["sub"]))
    return {"message": "회원탈퇴가 완료되었습니다"}
