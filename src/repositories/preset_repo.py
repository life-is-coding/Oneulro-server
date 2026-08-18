from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def get_preset(user_id: int) -> Optional[dict]:
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM oneulro.search_preset WHERE user_id = :user_id ORDER BY updated_at DESC LIMIT 1"),
            {"user_id": user_id},
        ).mappings().one_or_none()
    return dict(row) if row else None


def upsert_preset(user_id: int, data: dict) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    params = {"user_id": user_id, **data}
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT preset_id FROM oneulro.search_preset WHERE user_id = :user_id ORDER BY updated_at DESC LIMIT 1"),
            {"user_id": user_id},
        ).one_or_none()

        if existing:
            params["preset_id"] = existing[0]
            sql = text("""
                UPDATE oneulro.search_preset SET
                    name = :name, departure_station = :departure_station,
                    travel_days = :travel_days, companion_type = :companion_type,
                    budget_min = :budget_min, budget_max = :budget_max, pet_mode = :pet_mode,
                    theme_tags = CAST(:theme_tags AS jsonb), natural_language_memo = :natural_language_memo,
                    updated_at = CURRENT_TIMESTAMP
                WHERE preset_id = :preset_id
                RETURNING *
            """)
        else:
            sql = text("""
                INSERT INTO oneulro.search_preset
                    (user_id, name, departure_station, travel_days, companion_type, budget_min, budget_max, pet_mode, theme_tags, natural_language_memo)
                VALUES
                    (:user_id, :name, :departure_station, :travel_days, :companion_type, :budget_min, :budget_max, :pet_mode, CAST(:theme_tags AS jsonb), :natural_language_memo)
                RETURNING *
            """)

        row = conn.execute(sql, params).mappings().one()
        conn.commit()
    return dict(row)
