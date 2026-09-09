from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from typing import Optional

from src.core.dependencies import get_current_user
from src.application.session import create_redis_session, delete_redis_session
from src.adapter.outbound.user_repo import upsert_user, clear_refresh_token, soft_delete_user
from src.adapter.outbound.oauth_provider import get_oauth_provider
from src.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


@router.post("/{provider}/callback")
async def oauth_callback(provider: str, body: OAuthCallbackRequest, response: Response):
    """소셜 인가 코드를 받아 로그인 세션 토큰을 발급"""
    oauth_provider = get_oauth_provider(provider)
    token_response = await oauth_provider.exchange_code_for_token(body.code, body.state)
    profile = await oauth_provider.fetch_profile(token_response.access_token)

    user = upsert_user(
        provider=profile.provider,
        social_id=profile.social_id,
        nickname=profile.nickname,
        profile_image_url=profile.profile_image_url,
        refresh_token=token_response.refresh_token,
    )

    settings = get_settings()
    session_id = create_redis_session(user)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )

    return {
        "user": {
            "id": user["user_id"],
            "nickname": user["nickname"],
            "profile_image_url": user["profile_image_url"],
        },
    }


@router.get("/me")
async def me(user=Depends(get_current_user)):
    """세션 쿠키 유효성 검증 및 사용자 정보 반환"""
    return {
        "id": user.get("sub"),
        "nickname": user.get("nickname"),
        "profile_image_url": user.get("profile_image_url"),
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
):
    """로그아웃 — DB의 refresh_token 삭제"""
    settings = get_settings()
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    delete_redis_session(session_id)
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")
    clear_refresh_token(int(user["sub"]))
    return {"message": "로그아웃 되었습니다"}


@router.delete("/me")
async def delete_me(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
):
    """회원탈퇴 — soft delete"""
    settings = get_settings()
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    delete_redis_session(session_id)
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")
    soft_delete_user(int(user["sub"]))
    return {"message": "회원탈퇴가 완료되었습니다"}
