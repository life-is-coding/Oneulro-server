from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def get_course_detail(course_id: int) -> Optional[dict]:
    if engine is None:
        return None

    with engine.connect() as conn:
        course = conn.execute(
            text("SELECT course_id, user_id, title, departure_station, total_days, status, created_at FROM oneulro.course WHERE course_id = :id"),
            {"id": course_id},
        ).mappings().one_or_none()

        if not course:
            return None

        stops = conn.execute(
            text("""
                SELECT stop_id, day_number, sequence, station_name,
                       train_type, seat_class, arrive_at, depart_at, stay_minutes
                FROM oneulro.course_stop
                WHERE course_id = :id
                ORDER BY day_number, sequence
            """),
            {"id": course_id},
        ).mappings().all()

        stop_ids = [s["stop_id"] for s in stops]
        places_by_stop: dict = {sid: [] for sid in stop_ids}

        if stop_ids:
            rows = conn.execute(
                text("""
                    SELECT stop_id, place_id, name, category, address,
                           ST_X(location::geometry) AS lng,
                           ST_Y(location::geometry) AS lat,
                           pet_allowed, walk_minutes, image_url
                    FROM oneulro.place
                    WHERE stop_id = ANY(:ids)
                    ORDER BY place_id
                """),
                {"ids": stop_ids},
            ).mappings().all()
            for p in rows:
                places_by_stop[p["stop_id"]].append(dict(p))

    days: dict = {}
    for s in stops:
        d = s["day_number"]
        if d not in days:
            days[d] = []
        days[d].append({**dict(s), "places": places_by_stop[s["stop_id"]]})

    return {
        **dict(course),
        "days": [{"day_number": d, "stops": stops_list} for d, stops_list in sorted(days.items())],
    }


def create_course(user_id: int, title: str, departure_station: str, total_days: int, days: list) -> int:
    """코스 + 경유역 + 장소를 DB에 저장하고 course_id 반환"""
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                INSERT INTO oneulro.course (user_id, title, departure_station, total_days)
                VALUES (:user_id, :title, :departure_station, :total_days)
                RETURNING course_id
            """),
            {"user_id": user_id, "title": title, "departure_station": departure_station, "total_days": total_days},
        ).one()
        course_id = row[0]

        for day in days:
            day_number = day.get("day") or day.get("day_number", 1)
            row = conn.execute(
                text("""
                    INSERT INTO oneulro.course_stop (course_id, day_number, sequence, station_name)
                    VALUES (:course_id, :day_number, :sequence, :station_name)
                    RETURNING stop_id
                """),
                {"course_id": course_id, "day_number": day_number, "sequence": day_number, "station_name": day.get("city", "")},
            ).one()
            stop_id = row[0]

            for attraction in day.get("attractions", []):
                conn.execute(
                    text("""
                        INSERT INTO oneulro.place (stop_id, tour_content_id, name, category, address, image_url)
                        VALUES (:stop_id, :tour_content_id, :name, :category, :address, :image_url)
                    """),
                    {
                        "stop_id": stop_id,
                        "tour_content_id": str(attraction.get("contentid", "")),
                        "name": attraction.get("title", ""),
                        "category": attraction.get("category", ""),
                        "address": attraction.get("addr", ""),
                        "image_url": attraction.get("image", ""),
                    },
                )

        conn.commit()
    return course_id


def get_saved_courses(user_id: int) -> list[dict]:
    if engine is None:
        return []
    sql = text("""
        SELECT c.course_id, c.title, c.departure_station, c.total_days, c.status, c.created_at,
               sc.saved_at
        FROM oneulro.saved_course sc
        JOIN oneulro.course c ON c.course_id = sc.course_id
        WHERE sc.user_id = :user_id
        ORDER BY sc.saved_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).mappings().all()
    return [dict(r) for r in rows]


def save_course(user_id: int, course_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    sql = text("""
        INSERT INTO oneulro.saved_course (user_id, course_id)
        VALUES (:user_id, :course_id)
        ON CONFLICT (user_id, course_id) DO NOTHING
        RETURNING saved_id, saved_at
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id, "course_id": course_id}).mappings().one_or_none()
        conn.commit()
    if not row:
        raise HTTPException(status_code=409, detail="이미 저장된 코스입니다")
    return dict(row)


def unsave_course(user_id: int, course_id: int) -> None:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    sql = text("""
        DELETE FROM oneulro.saved_course
        WHERE user_id = :user_id AND course_id = :course_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"user_id": user_id, "course_id": course_id})
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="저장된 코스가 없습니다")
