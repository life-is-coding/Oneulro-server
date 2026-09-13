from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text

from src.db import engine


def create_notification(user_id: int, notification_type: str, title: str, content: Optional[str] = None, target_type: Optional[str] = None, target_id: Optional[int] = None, dedupe_key: Optional[str] = None) -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO oneulro.notification
                (user_id, notification_type, title, content, target_type, target_id, dedupe_key)
            SELECT
                :user_id, :notification_type, :title, :content, :target_type, :target_id, :dedupe_key
            WHERE COALESCE((
                SELECT enabled FROM oneulro.user_notification_setting
                WHERE user_id = :user_id AND notification_type = :notification_type
            ), TRUE)
            ON CONFLICT (user_id, dedupe_key) DO NOTHING
        """), {
            "user_id": user_id, "notification_type": notification_type,
            "title": title, "content": content, "target_type": target_type,
            "target_id": target_id, "dedupe_key": dedupe_key,
        })


def list_notifications(user_id: int, notification_type: Optional[str] = None) -> list[dict]:
    if engine is None:
        return []
    type_filter = "AND notification_type = :notification_type" if notification_type else ""
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT notification_id, notification_type, title, content, target_type,
                   target_id, read_at, created_at
            FROM oneulro.notification
            WHERE user_id = :user_id {type_filter}
            ORDER BY created_at DESC
            LIMIT 100
        """), {"user_id": user_id, "notification_type": notification_type}).mappings().all()
    return [dict(row) for row in rows]


def count_unread_notifications(user_id: int) -> int:
    if engine is None:
        return 0
    with engine.connect() as conn:
        count = conn.execute(text("""
            SELECT COUNT(*)
            FROM oneulro.notification
            WHERE user_id = :user_id AND read_at IS NULL
        """), {"user_id": user_id}).scalar_one()
    return int(count)


def mark_notification_read(user_id: int, notification_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE oneulro.notification SET read_at = COALESCE(read_at, NOW())
            WHERE notification_id = :notification_id AND user_id = :user_id
            RETURNING notification_id, read_at
        """), {"notification_id": notification_id, "user_id": user_id}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
    return dict(row)


def mark_all_notifications_read(user_id: int) -> int:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE oneulro.notification SET read_at = NOW()
            WHERE user_id = :user_id AND read_at IS NULL
        """), {"user_id": user_id})
    return result.rowcount


def delete_notification(user_id: int, notification_id: int) -> None:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        result = conn.execute(text("""
            DELETE FROM oneulro.notification
            WHERE notification_id = :notification_id AND user_id = :user_id
        """), {"notification_id": notification_id, "user_id": user_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")


def delete_all_notifications(user_id: int) -> int:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        result = conn.execute(text("""
            DELETE FROM oneulro.notification WHERE user_id = :user_id
        """), {"user_id": user_id})
    return result.rowcount
