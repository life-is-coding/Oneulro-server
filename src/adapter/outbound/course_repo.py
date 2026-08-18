from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def get_course_detail(course_id: int) -> Optional[dict]:
    if engine is None:
        return None

    with engine.connect() as conn:
        course = conn.execute(
            text("SELECT course_id, user_id, title, departure_station, total_days, 'DONE' AS status, created_at FROM oneulro.course WHERE course_id = :id"),
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

        print(f"stop_ids: {stop_ids}")  # Debugging line to check stop_ids
        print(f"places_by_stop: {places_by_stop}")  # Debugging line to check places_by_stop

        if stop_ids:
            rows = conn.execute(
                text("""
                    SELECT stop_id, place_id, name, category, address, lat, lng,
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
                    INSERT INTO oneulro.course_stop
                        (course_id, day_number, sequence, station_name, lat, lng)
                    VALUES (:course_id, :day_number, :sequence, :station_name, :lat, :lng)
                    RETURNING stop_id
                """),
                {
                    "course_id": course_id,
                    "day_number": day_number,
                    "sequence": 1,
                    "station_name": day.get("city", ""),
                    "lat": day.get("lat"),
                    "lng": day.get("lng"),
                },
            ).one()
            stop_id = row[0]

            for place_sequence, attraction in enumerate(day.get("attractions", []), start=1):
                conn.execute(
                    text("""
                        INSERT INTO oneulro.place
                            (stop_id, name, category, address, lat, lng, sequence, image_url, area_cd, signgu_cd)
                        VALUES
                            (:stop_id, :name, :category, :address, :lat, :lng, :sequence, :image_url, :area_cd, :signgu_cd)
                    """),
                    {
                        "stop_id": stop_id,
                        "name": attraction.get("title", ""),
                        "category": attraction.get("category", ""),
                        "address": attraction.get("addr", ""),
                        "lat": attraction.get("mapy"),
                        "lng": attraction.get("mapx"),
                        "sequence": place_sequence,
                        "image_url": attraction.get("image", ""),
                        "area_cd": attraction.get("area_cd"),
                        "signgu_cd": attraction.get("signgu_cd"),
                    },
                )

        conn.commit()
    return course_id


def get_place(place_id: int) -> Optional[dict]:
    """장소 단건 상세 조회"""
    if engine is None:
        return None
    sql = text("""
        SELECT place_id, stop_id, name, category, address, lat, lng, sequence,
               image_url, opening_hours, walk_minutes, congestion_score, weather_summary,
               pet_allowed, indoor_yn, free_yn, area_cd, signgu_cd, created_at, updated_at
        FROM oneulro.place
        WHERE place_id = :place_id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"place_id": place_id}).mappings().one_or_none()
    return dict(row) if row else None


def get_saved_courses(user_id: int) -> list[dict]:
    if engine is None:
        return []
    sql = text("""
        SELECT c.course_id, c.title, c.departure_station, c.total_days, 'DONE' AS status, c.created_at,
               cb.created_at AS saved_at
        FROM oneulro.course_bookmark cb
        JOIN oneulro.course c ON c.course_id = cb.course_id
        WHERE cb.user_id = :user_id
        ORDER BY cb.created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).mappings().all()
    return [dict(r) for r in rows]


def save_course(user_id: int, course_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    sql = text("""
        INSERT INTO oneulro.course_bookmark (user_id, course_id)
        VALUES (:user_id, :course_id)
        ON CONFLICT (user_id, course_id) DO NOTHING
        RETURNING course_id, created_at AS saved_at
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
        DELETE FROM oneulro.course_bookmark
        WHERE user_id = :user_id AND course_id = :course_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"user_id": user_id, "course_id": course_id})
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="저장된 코스가 없습니다")
