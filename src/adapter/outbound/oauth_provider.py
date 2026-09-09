from dataclasses import dataclass
from typing import Optional, Protocol

import httpx
from fastapi import HTTPException

from src.core.config import get_settings


@dataclass
class OAuthToken:
    access_token: str
    refresh_token: Optional[str] = None


@dataclass
class OAuthProfile:
    provider: str
    social_id: str
    nickname: str
    profile_image_url: Optional[str]


class OAuthProvider(Protocol):
    provider: str

    async def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> OAuthToken:
        ...

    async def fetch_profile(self, access_token: str) -> OAuthProfile:
        ...


class KakaoOAuthProvider:
    provider = "KAKAO"
    token_url = "https://kauth.kakao.com/oauth/token"
    profile_url = "https://kapi.kakao.com/v2/user/me"

    async def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> OAuthToken:
        settings = get_settings()
        if not settings.KAKAO_REST_API_KEY or not settings.KAKAO_REDIRECT_URI:
            raise HTTPException(status_code=500, detail="카카오 로그인 설정이 누락되었습니다")

        data = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        }
        if settings.KAKAO_CLIENT_SECRET:
            data["client_secret"] = settings.KAKAO_CLIENT_SECRET

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"카카오 토큰 교환 실패: {response.text}")

        body = response.json()
        return OAuthToken(access_token=body["access_token"], refresh_token=body.get("refresh_token"))

    async def fetch_profile(self, access_token: str) -> OAuthProfile:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.profile_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"카카오 프로필 조회 실패: {response.text}")

        payload = response.json()
        kakao_account = payload.get("kakao_account", {})
        profile = kakao_account.get("profile", {})
        social_id = payload.get("id")
        if not social_id:
            raise HTTPException(status_code=401, detail="카카오 사용자 ID를 확인할 수 없습니다")
        return OAuthProfile(
            provider=self.provider,
            social_id=str(social_id),
            nickname=profile.get("nickname") or "여행자",
            profile_image_url=profile.get("profile_image_url"),
        )


class NaverOAuthProvider:
    provider = "NAVER"
    token_url = "https://nid.naver.com/oauth2.0/token"
    profile_url = "https://openapi.naver.com/v1/nid/me"

    async def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> OAuthToken:
        settings = get_settings()
        if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
            raise HTTPException(status_code=500, detail="네이버 로그인 설정이 누락되었습니다")
        if not state:
            raise HTTPException(status_code=400, detail="네이버 state 값이 누락되었습니다")

        params = {
            "grant_type": "authorization_code",
            "client_id": settings.NAVER_CLIENT_ID,
            "client_secret": settings.NAVER_CLIENT_SECRET,
            "code": code,
            "state": state,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self.token_url, params=params)

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"네이버 토큰 교환 실패: {response.text}")

        body = response.json()
        if "access_token" not in body:
            raise HTTPException(status_code=401, detail=f"네이버 토큰 교환 실패: {body}")
        return OAuthToken(access_token=body["access_token"], refresh_token=body.get("refresh_token"))

    async def fetch_profile(self, access_token: str) -> OAuthProfile:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.profile_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"네이버 프로필 조회 실패: {response.text}")

        profile = response.json().get("response", {})
        social_id = profile.get("id")
        if not social_id:
            raise HTTPException(status_code=401, detail="네이버 사용자 ID를 확인할 수 없습니다")
        return OAuthProfile(
            provider=self.provider,
            social_id=str(social_id),
            nickname=profile.get("nickname") or profile.get("name") or "여행자",
            profile_image_url=profile.get("profile_image"),
        )


class GoogleOAuthProvider:
    provider = "GOOGLE"
    token_url = "https://oauth2.googleapis.com/token"
    profile_url = "https://openidconnect.googleapis.com/v1/userinfo"

    async def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> OAuthToken:
        settings = get_settings()
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET or not settings.GOOGLE_REDIRECT_URI:
            raise HTTPException(status_code=500, detail="구글 로그인 설정이 누락되었습니다")

        data = {
            "grant_type": "authorization_code",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"구글 토큰 교환 실패: {response.text}")

        body = response.json()
        return OAuthToken(access_token=body["access_token"], refresh_token=body.get("refresh_token"))

    async def fetch_profile(self, access_token: str) -> OAuthProfile:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.profile_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail=f"구글 프로필 조회 실패: {response.text}")

        profile = response.json()
        social_id = profile.get("sub")
        if not social_id:
            raise HTTPException(status_code=401, detail="구글 사용자 ID를 확인할 수 없습니다")
        return OAuthProfile(
            provider=self.provider,
            social_id=str(social_id),
            nickname=profile.get("name") or profile.get("email") or "여행자",
            profile_image_url=profile.get("picture"),
        )


def get_oauth_provider(provider: str) -> OAuthProvider:
    providers = {
        "kakao": KakaoOAuthProvider(),
        "naver": NaverOAuthProvider(),
        "google": GoogleOAuthProvider(),
    }
    oauth_provider = providers.get(provider.lower())
    if oauth_provider is None:
        raise HTTPException(status_code=404, detail="지원하지 않는 소셜 로그인입니다")
    return oauth_provider
