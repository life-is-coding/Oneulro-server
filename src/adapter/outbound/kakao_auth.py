from src.adapter.outbound.oauth_provider import KakaoOAuthProvider


async def exchange_code_for_token(code: str) -> dict:
    """카카오 인가 코드를 액세스 토큰으로 교환"""
    token = await KakaoOAuthProvider().exchange_code_for_token(code)
    return {
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
    }


async def fetch_kakao_profile(access_token: str) -> dict:
    """액세스 토큰으로 카카오 사용자 프로필 조회"""
    profile = await KakaoOAuthProvider().fetch_profile(access_token)
    return {
        "kakao_id": profile.social_id,
        "nickname": profile.nickname,
        "profile_image_url": profile.profile_image_url,
    }
