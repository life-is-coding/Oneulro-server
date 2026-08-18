from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def _require_engine():
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")


def create_course(
    user_id: int,
    title: Optional[str],
    alias: Optional[str],
    departure_station: str,
    total_days: int,
    recommendation_reason: Optional[str],
    stops: list,
    preset_id: Optional[int] = None,
    start_date=None,
    end_date=None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
) -> int:
    """코스 + 경유역 + 장소를 DB에 저장하고 course_id 반환"""
    _require_engine()

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                INSERT INTO oneulro.course
                    (user_id, preset_id, title, alias, departure_station, start_date, end_date,
                     total_days, budget_min, budget_max, recommendation_reason)
                VALUES
                    (:user_id, :preset_id, :title, :alias, :departure_station, :start_date, :end_date,
                     :total_days, :budget_min, :budget_max, :recommendation_reason)
                RETURNING course_id
            """),
            {
                "user_id": user_id,
                "preset_id": preset_id,
                "title": title,
                "alias": alias,
                "departure_station": departure_station,
                "start_date": start_date,
                "end_date": end_date,
                "total_days": total_days,
                "budget_min": budget_min,
                "budget_max": budget_max,
                "recommendation_reason": recommendation_reason,
            },
        ).one()
        course_id = row[0]

        for stop in stops:
            row = conn.execute(
                text("""
                    INSERT INTO oneulro.course_stop
                        (course_id, day_number, sequence, station_name, lat, lng,
                         image_url, congestion_score, is_benefit_station, travel_minutes,
                         train_type, train_number, seat_class, arrive_at, depart_at, stay_minutes)
                    VALUES
                        (:course_id, :day_number, :sequence, :station_name, :lat, :lng,
                         :image_url, :congestion_score, :is_benefit_station, :travel_minutes,
                         :train_type, :train_number, :seat_class, :arrive_at, :depart_at, :stay_minutes)
                    RETURNING stop_id
                """),
                {
                    "course_id": course_id,
                    "day_number": stop.get("day_number", 1),
                    "sequence": stop.get("sequence", 1),
                    "station_name": stop.get("station_name", ""),
                    "lat": stop.get("lat"),
                    "lng": stop.get("lng"),
                    "image_url": stop.get("image_url"),
                    "congestion_score": stop.get("congestion_score"),
                    "is_benefit_station": stop.get("is_benefit_station", False),
                    "travel_minutes": stop.get("travel_minutes"),
                    "train_type": stop.get("train_type"),
                    "train_number": stop.get("train_number"),
                    "seat_class": stop.get("seat_class"),
                    "arrive_at": stop.get("arrive_at"),
                    "depart_at": stop.get("depart_at"),
                    "stay_minutes": stop.get("stay_minutes"),
                },
            ).one()
            stop_id = row[0]

            for place_sequence, place in enumerate(stop.get("places", []), start=1):
                _insert_place(conn, stop_id, place_sequence, place)

        conn.commit()
    return course_id


def _insert_place(conn, stop_id: int, sequence: int, place: dict) -> int:
    row = conn.execute(
        text("""
            INSERT INTO oneulro.place
                (stop_id, name, category, address, lat, lng, sequence,
                 image_url, opening_hours, walk_minutes, congestion_score, weather_summary,
                 pet_allowed, indoor_yn, free_yn)
            VALUES
                (:stop_id, :name, :category, :address, :lat, :lng, :sequence,
                 :image_url, :opening_hours, :walk_minutes, :congestion_score, :weather_summary,
                 :pet_allowed, :indoor_yn, :free_yn)
            RETURNING place_id
        """),
        {
            "stop_id": stop_id,
            "name": place.get("name", ""),
            "category": place.get("category"),
            "address": place.get("address"),
            "lat": place.get("lat"),
            "lng": place.get("lng"),
            "sequence": sequence,
            "image_url": place.get("image_url"),
            "opening_hours": place.get("opening_hours"),
            "walk_minutes": place.get("walk_minutes"),
            "congestion_score": place.get("congestion_score"),
            "weather_summary": place.get("weather_summary"),
            "pet_allowed": place.get("pet_allowed", False),
            "indoor_yn": place.get("indoor_yn", False),
            "free_yn": place.get("free_yn", False),
        },
    ).one()
    return row[0]


_COURSE_COLUMN_LIST = [
    "course_id", "user_id", "preset_id", "title", "alias", "departure_station",
    "start_date", "end_date", "total_days", "budget_min", "budget_max",
    "recommendation_reason", "visibility", "view_count", "created_at",
]
_COURSE_COLUMNS = ", ".join(_COURSE_COLUMN_LIST)

_STOP_COLUMNS = """
    stop_id, day_number, sequence, station_name, lat, lng,
    image_url, congestion_score, is_benefit_station, travel_minutes,
    train_type, train_number, seat_class, arrive_at, depart_at, stay_minutes
"""

_PLACE_COLUMNS = """
    place_id, stop_id, name, category, address, lat, lng, sequence,
    image_url, opening_hours, walk_minutes, congestion_score, weather_summary,
    pet_allowed, indoor_yn, free_yn
"""


def get_course_detail(course_id: int, user_id: int) -> Optional[dict]:
    """소유자 또는 공개(PUBLIC) 코스만 조회 가능. 역별로 그룹핑된 결과 반환."""
    _require_engine()

    with engine.connect() as conn:
        course = conn.execute(
            text(f"SELECT {_COURSE_COLUMNS} FROM oneulro.course WHERE course_id = :id AND deleted_at IS NULL"),
            {"id": course_id},
        ).mappings().one_or_none()

        if not course:
            return None
        if course["user_id"] != user_id and course["visibility"] != "PUBLIC":
            raise HTTPException(status_code=403, detail="이 코스를 조회할 권한이 없습니다")

        stops = conn.execute(
            text(f"""
                SELECT {_STOP_COLUMNS}
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
                text(f"""
                    SELECT {_PLACE_COLUMNS}
                    FROM oneulro.place
                    WHERE stop_id = ANY(:ids)
                    ORDER BY sequence
                """),
                {"ids": stop_ids},
            ).mappings().all()
            for p in rows:
                places_by_stop[p["stop_id"]].append(dict(p))

    stations = [
        {**dict(s), "places": places_by_stop[s["stop_id"]]}
        for s in stops
    ]

    return {**dict(course), "stations": stations}


def update_alias(course_id: int, user_id: int, alias: str) -> dict:
    _require_engine()
    sql = text("""
        UPDATE oneulro.course
        SET alias = :alias, updated_at = CURRENT_TIMESTAMP
        WHERE course_id = :course_id AND user_id = :user_id AND deleted_at IS NULL
        RETURNING course_id, title, alias
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"course_id": course_id, "user_id": user_id, "alias": alias}).mappings().one_or_none()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
    return dict(row)


def list_bookmarked_courses(user_id: int) -> list[dict]:
    if engine is None:
        return []
    sql = text(f"""
        SELECT {', '.join('c.' + col for col in _COURSE_COLUMN_LIST)},
               b.created_at AS bookmarked_at
        FROM oneulro.course_bookmark b
        JOIN oneulro.course c ON c.course_id = b.course_id
        WHERE b.user_id = :user_id AND c.deleted_at IS NULL
        ORDER BY b.created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"user_id": user_id}).mappings().all()
    return [dict(r) for r in rows]


def bookmark_course(user_id: int, course_id: int) -> dict:
    _require_engine()
    sql = text("""
        INSERT INTO oneulro.course_bookmark (user_id, course_id)
        VALUES (:user_id, :course_id)
        ON CONFLICT (user_id, course_id) DO NOTHING
        RETURNING user_id, course_id, created_at
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id, "course_id": course_id}).mappings().one_or_none()
        conn.commit()
    if not row:
        raise HTTPException(status_code=409, detail="이미 저장된 코스입니다")
    return dict(row)


def unbookmark_course(user_id: int, course_id: int) -> None:
    _require_engine()
    sql = text("""
        DELETE FROM oneulro.course_bookmark
        WHERE user_id = :user_id AND course_id = :course_id
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"user_id": user_id, "course_id": course_id})
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="저장된 코스가 없습니다")


def _assert_stop_owned(conn, stop_id: int, user_id: int) -> int:
    """stop_id가 user_id 소유의 코스에 속하는지 확인, 해당 course_id 반환."""
    row = conn.execute(
        text("""
            SELECT c.course_id
            FROM oneulro.course_stop cs
            JOIN oneulro.course c ON c.course_id = cs.course_id
            WHERE cs.stop_id = :stop_id AND c.user_id = :user_id AND c.deleted_at IS NULL
        """),
        {"stop_id": stop_id, "user_id": user_id},
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="역 정보를 찾을 수 없습니다")
    return row[0]


def add_place(course_id: int, user_id: int, stop_id: int, place: dict) -> dict:
    _require_engine()
    with engine.connect() as conn:
        owning_course_id = _assert_stop_owned(conn, stop_id, user_id)
        if owning_course_id != course_id:
            raise HTTPException(status_code=404, detail="해당 코스에 속한 역이 아닙니다")

        next_seq = conn.execute(
            text("SELECT COALESCE(MAX(sequence), 0) + 1 FROM oneulro.place WHERE stop_id = :stop_id"),
            {"stop_id": stop_id},
        ).scalar_one()

        place_id = _insert_place(conn, stop_id, next_seq, place)
        conn.commit()

        row = conn.execute(
            text(f"SELECT {_PLACE_COLUMNS} FROM oneulro.place WHERE place_id = :id"),
            {"id": place_id},
        ).mappings().one()
    return dict(row)


def delete_place(course_id: int, user_id: int, place_id: int) -> None:
    _require_engine()
    sql = text("""
        DELETE FROM oneulro.place p
        USING oneulro.course_stop cs, oneulro.course c
        WHERE p.place_id = :place_id
          AND p.stop_id = cs.stop_id
          AND cs.course_id = c.course_id
          AND c.course_id = :course_id
          AND c.user_id = :user_id
          AND c.deleted_at IS NULL
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"place_id": place_id, "course_id": course_id, "user_id": user_id})
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다")


def replace_stop_places(course_id: int, user_id: int, stop_id: int, places: list) -> list[dict]:
    """역 하나의 장소를 통째로 교체 (역별 재생성)."""
    _require_engine()
    with engine.connect() as conn:
        owning_course_id = _assert_stop_owned(conn, stop_id, user_id)
        if owning_course_id != course_id:
            raise HTTPException(status_code=404, detail="해당 코스에 속한 역이 아닙니다")

        conn.execute(text("DELETE FROM oneulro.place WHERE stop_id = :stop_id"), {"stop_id": stop_id})
        place_ids = [_insert_place(conn, stop_id, seq, p) for seq, p in enumerate(places, start=1)]
        conn.commit()

        rows = conn.execute(
            text(f"SELECT {_PLACE_COLUMNS} FROM oneulro.place WHERE place_id = ANY(:ids) ORDER BY sequence"),
            {"ids": place_ids},
        ).mappings().all()
    return [dict(r) for r in rows]


def replace_all_places(course_id: int, user_id: int, places_by_stop: dict[int, list]) -> None:
    """코스 전체 장소를 통째로 교체 (전체 재생성)."""
    for stop_id, places in places_by_stop.items():
        replace_stop_places(course_id, user_id, stop_id, places)


def get_course_stops(course_id: int, user_id: int) -> list[dict]:
    """소유권 확인 후 코스의 역 목록만 반환 (재생성 시 각 역의 좌표를 얻기 위함)."""
    _require_engine()
    with engine.connect() as conn:
        owner = conn.execute(
            text("SELECT user_id FROM oneulro.course WHERE course_id = :id AND deleted_at IS NULL"),
            {"id": course_id},
        ).one_or_none()
        if not owner:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
        if owner[0] != user_id:
            raise HTTPException(status_code=403, detail="이 코스를 수정할 권한이 없습니다")

        rows = conn.execute(
            text(f"SELECT {_STOP_COLUMNS} FROM oneulro.course_stop WHERE course_id = :id ORDER BY day_number, sequence"),
            {"id": course_id},
        ).mappings().all()
    return [dict(r) for r in rows]
