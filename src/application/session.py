import json
import secrets
from typing import Optional

from fastapi import HTTPException

from src.core.config import get_settings
from src.core.redis import get_redis_client

SESSION_KEY_PREFIX = "session:"


def create_redis_session(user: dict) -> str:
    settings = get_settings()
    session_id = secrets.token_urlsafe(32)
    payload = {
        "sub": str(user["user_id"]),
        "provider": user["social_provider"],
        "social_id": user["social_id"],
        "nickname": user["nickname"],
        "profile_image_url": user.get("profile_image_url"),
    }
    get_redis_client().setex(
        f"{SESSION_KEY_PREFIX}{session_id}",
        settings.SESSION_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False),
    )
    return session_id


def get_redis_session(session_id: Optional[str]) -> dict:
    if not session_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    raw = get_redis_client().get(f"{SESSION_KEY_PREFIX}{session_id}")
    if not raw:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")


def delete_redis_session(session_id: Optional[str]) -> None:
    if session_id:
        get_redis_client().delete(f"{SESSION_KEY_PREFIX}{session_id}")


def update_redis_session(session_id: Optional[str], updates: dict) -> None:
    if not session_id:
        return

    key = f"{SESSION_KEY_PREFIX}{session_id}"
    client = get_redis_client()
    raw = client.get(key)
    if not raw:
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return

    payload.update({key: value for key, value in updates.items() if value is not None})
    ttl = client.ttl(key)
    if ttl and ttl > 0:
        client.setex(key, ttl, json.dumps(payload, ensure_ascii=False))
