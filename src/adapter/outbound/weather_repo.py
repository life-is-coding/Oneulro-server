from typing import Optional

from sqlalchemy import text

from src.db import engine


def get_course_weather_destination(course_id: int, user_id: int) -> Optional[dict]:
    if engine is None:
        return None
    sql = text("""
        SELECT cs.station_name, cs.lat, cs.lng, cs.day_number, cs.sequence
        FROM oneulro.course c
        JOIN oneulro.course_stop cs ON cs.course_id = c.course_id
        WHERE c.course_id = :course_id
          AND c.user_id = :user_id
          AND c.deleted_at IS NULL
          AND cs.lat IS NOT NULL
          AND cs.lng IS NOT NULL
        ORDER BY cs.day_number, cs.sequence
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"course_id": course_id, "user_id": user_id}).mappings().one_or_none()
    return dict(row) if row else None


def get_home_weather_destinations() -> list[dict]:
    if engine is None:
        return []
    sql = text("""
        SELECT c.course_id,
               (c.start_date + (cs.day_number - 1))::date AS start_date,
               c.departure_station,
               cs.station_name,
               cs.lat,
               cs.lng,
               cs.day_number,
               cs.sequence
        FROM oneulro.course c
        JOIN oneulro.course_stop cs ON cs.course_id = c.course_id
        JOIN oneulro.app_user u ON u.user_id = c.user_id
        WHERE u.social_provider = 'SAMPLE'
          AND u.social_id = 'weather-sample-user'
          AND c.title = '전국 주요역 날씨 샘플'
          AND c.deleted_at IS NULL
          AND cs.lat IS NOT NULL
          AND cs.lng IS NOT NULL
        ORDER BY cs.day_number, cs.sequence
    """)
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(sql).mappings().all()]
