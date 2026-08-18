from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def upsert_user(
    kakao_id: str,
    nickname: str,
    profile_image_url: Optional[str],
    refresh_token: Optional[str],
) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    sql = text("""
        INSERT INTO oneulro.app_user (social_provider, social_id, nickname, profile_image_url, refresh_token)
        VALUES ('KAKAO', :kakao_id, :nickname, :profile_image_url, :refresh_token)
        ON CONFLICT (social_provider, social_id) DO UPDATE SET
            nickname          = EXCLUDED.nickname,
            profile_image_url = EXCLUDED.profile_image_url,
            refresh_token     = EXCLUDED.refresh_token,
            deleted_at        = NULL
        RETURNING user_id, social_id AS kakao_id, nickname, profile_image_url
    """)

    with engine.connect() as conn:
        row = conn.execute(sql, {
            "kakao_id": kakao_id,
            "nickname": nickname,
            "profile_image_url": profile_image_url,
            "refresh_token": refresh_token,
        }).mappings().one()
        conn.commit()

    return dict(row)


def get_user(user_id: int) -> Optional[dict]:
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT user_id, social_id AS kakao_id, nickname, profile_image_url, created_at FROM oneulro.app_user WHERE user_id = :user_id AND deleted_at IS NULL"),
            {"user_id": user_id},
        ).mappings().one_or_none()
    return dict(row) if row else None


def update_user(user_id: int, nickname: Optional[str], profile_image_url: Optional[str]) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    sets = []
    params: dict = {"user_id": user_id}
    if nickname is not None:
        sets.append("nickname = :nickname")
        params["nickname"] = nickname
    if profile_image_url is not None:
        sets.append("profile_image_url = :profile_image_url")
        params["profile_image_url"] = profile_image_url
    if not sets:
        raise HTTPException(status_code=400, detail="수정할 항목이 없습니다")
    sql = text(f"UPDATE oneulro.app_user SET {', '.join(sets)} WHERE user_id = :user_id AND deleted_at IS NULL RETURNING user_id, nickname, profile_image_url")
    with engine.connect() as conn:
        row = conn.execute(sql, params).mappings().one_or_none()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return dict(row)


def clear_refresh_token(user_id: int) -> None:
    if engine is None:
        return
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE oneulro.app_user SET refresh_token = NULL WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        conn.commit()


def soft_delete_user(user_id: int) -> None:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE oneulro.app_user SET deleted_at = CURRENT_TIMESTAMP, refresh_token = NULL WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        conn.commit()
