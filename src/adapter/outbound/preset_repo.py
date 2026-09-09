from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def _budget_bounds(budget_range: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if budget_range == "저예산":
        return 0, 100000
    if budget_range == "표준":
        return 100000, 300000
    if budget_range == "넉넉하게":
        return 300000, None
    return None, None


def _normalize_preset_data(data: dict) -> dict:
    budget_min = data.get("budget_min")
    budget_max = data.get("budget_max")
    if budget_min is None and budget_max is None:
        budget_min, budget_max = _budget_bounds(data.get("budget_range"))

    pet_mode = data.get("pet_mode")
    if pet_mode is None:
        pet_mode = "WITH_PET" if data.get("pet_allowed") else "NONE"

    return {
        "departure_station": data.get("departure_station") or "서울역",
        "travel_days": data.get("travel_days"),
        "companion_type": data.get("companion_type"),
        "budget_min": budget_min,
        "budget_max": budget_max,
        "pet_mode": pet_mode,
        "theme_tags": data.get("theme_tags"),
        "natural_language_memo": data.get("natural_language_memo"),
    }


def get_preset(user_id: int) -> Optional[dict]:
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT *
                FROM oneulro.search_preset
                WHERE user_id = :user_id
                ORDER BY updated_at DESC, preset_id DESC
                LIMIT 1
            """),
            {"user_id": user_id},
        ).mappings().one_or_none()
    return dict(row) if row else None


def upsert_preset(user_id: int, data: dict) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    params = {"user_id": user_id, **_normalize_preset_data(data)}
    with engine.connect() as conn:
        existing = conn.execute(
            text("""
                SELECT preset_id
                FROM oneulro.search_preset
                WHERE user_id = :user_id
                ORDER BY updated_at DESC, preset_id DESC
                LIMIT 1
            """),
            {"user_id": user_id},
        ).one_or_none()

        if existing:
            sql = text("""
                UPDATE oneulro.search_preset SET
                    departure_station = :departure_station,
                    travel_days = :travel_days, companion_type = :companion_type,
                    budget_min = :budget_min, budget_max = :budget_max,
                    pet_mode = :pet_mode,
                    theme_tags = CAST(:theme_tags AS jsonb),
                    natural_language_memo = :natural_language_memo,
                    updated_at = NOW()
                WHERE preset_id = :preset_id
                RETURNING *
            """)
            params["preset_id"] = existing[0]
        else:
            sql = text("""
                INSERT INTO oneulro.search_preset (
                    user_id, departure_station, travel_days, companion_type,
                    budget_min, budget_max, pet_mode, theme_tags, natural_language_memo
                )
                VALUES (
                    :user_id, :departure_station, :travel_days, :companion_type,
                    :budget_min, :budget_max, :pet_mode, CAST(:theme_tags AS jsonb), :natural_language_memo
                )
                RETURNING *
            """)

        row = conn.execute(sql, params).mappings().one()
        conn.commit()
    return dict(row)
