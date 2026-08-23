from typing import Optional

from fastapi import Header, HTTPException

from src.application.session import decode_session_token


# TODO: 로그인 토큰 이슈 해결되면 원상복구 — 지금은 토큰 없거나 깨져도 막지 않고 테스트 유저(user_id=1)로 통과시킴
_DEV_FALLBACK_USER = {"sub": "1", "kakao_id": "test-social-id", "nickname": "테스터", "profile_image_url": None}


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        return _DEV_FALLBACK_USER
    try:
        return decode_session_token(authorization.removeprefix("Bearer "))
    except Exception:
        return _DEV_FALLBACK_USER
