import httpx
from fastapi import HTTPException

from src.core.config import get_settings

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_ME_URL = "https://kapi.kakao.com/v2/user/me"


async def exchange_code_for_token(code: str) -> dict:
    """카카오 인가 코드를 액세스 토큰으로 교환"""
    settings = get_settings()
    client_id = settings.KAKAO_REST_API_KEY
    client_secret = settings.KAKAO_CLIENT_SECRET
    redirect_uri = settings.KAKAO_REDIRECT_URI

    if not client_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="카카오 로그인 설정이 누락되었습니다")

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            KAKAO_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"카카오 토큰 교환 실패: {response.text}",
        )

    body = response.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token"),
    }


async def fetch_kakao_profile(access_token: str) -> dict:
    """액세스 토큰으로 카카오 사용자 프로필 조회"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            KAKAO_USER_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail=f"카카오 프로필 조회 실패: {response.text}",
        )

    payload = response.json()
    kakao_account = payload.get("kakao_account", {})
    profile = kakao_account.get("profile", {})

    return {
        "kakao_id": str(payload.get("id")),
        "nickname": profile.get("nickname", "여행자"),
        "profile_image_url": profile.get("profile_image_url"),
    }
