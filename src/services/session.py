import os
import time

import jwt

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_SECONDS = 60 * 60 * 24 * 30  # 30일


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET 환경변수가 설정되지 않았습니다")
    return secret


def create_session_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user["user_id"]),
        "social_id": user["social_id"],
        "nickname": user["nickname"],
        "profile_image_url": user.get("profile_image_url"),
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
