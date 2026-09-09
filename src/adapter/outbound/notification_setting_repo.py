from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine

DEFAULT_NOTIFICATION_SETTINGS: dict[str, bool] = {
    "travel": True,
    "train": True,
    "community": False,
}


def get_notification_settings(user_id: int) -> list[dict]:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT notification_type, enabled
            FROM oneulro.user_notification_setting
            WHERE user_id = :user_id
        """), {"user_id": user_id}).mappings().all()

    saved = {row["notification_type"]: row["enabled"] for row in rows}
    merged = {**DEFAULT_NOTIFICATION_SETTINGS, **saved}
    return [
        {"notification_type": notification_type, "enabled": enabled}
        for notification_type, enabled in merged.items()
    ]


def update_notification_settings(user_id: int, settings: dict[str, bool]) -> list[dict]:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    allowed_types = set(DEFAULT_NOTIFICATION_SETTINGS.keys())
    unknown_types = set(settings.keys()) - allowed_types
    if unknown_types:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 알림 타입입니다: {', '.join(sorted(unknown_types))}")

    with engine.connect() as conn:
        for notification_type, enabled in settings.items():
            conn.execute(text("""
                INSERT INTO oneulro.user_notification_setting (user_id, notification_type, enabled)
                VALUES (:user_id, :notification_type, :enabled)
                ON CONFLICT (user_id, notification_type)
                DO UPDATE SET enabled = EXCLUDED.enabled,
                              updated_at = NOW()
            """), {
                "user_id": user_id,
                "notification_type": notification_type,
                "enabled": enabled,
            })
        conn.commit()

    return get_notification_settings(user_id)
