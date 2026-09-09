from typing import Optional

from sqlalchemy import text
from fastapi import HTTPException

from src.db import engine


def get_course_detail(course_id: int) -> Optional[dict]:
    if engine is None:
        return None

    with engine.connect() as conn:
        has_status = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'status'
            )
        """)).scalar()
        has_deleted_at = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'deleted_at'
            )
        """)).scalar()
        status_select = "status" if has_status else "'DONE'"
        has_visibility = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'visibility'
            )
        """)).scalar()
        visibility_select = "visibility" if has_visibility else "'PRIVATE'"
        deleted_filter = "AND deleted_at IS NULL" if has_deleted_at else ""
        course = conn.execute(
            text(f"SELECT course_id, user_id, title, departure_station, total_days, {status_select} AS status, {visibility_select} AS visibility, created_at FROM oneulro.course WHERE course_id = :id {deleted_filter}"),
            {"id": course_id},
        ).mappings().one_or_none()

        if not course:
            return None

        stops = conn.execute(
            text("""
                SELECT stop_id, day_number, sequence, station_name, lat, lng,
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
    with engine.connect() as conn:
        has_start_date = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'start_date'
            )
        """)).scalar()
        start_date_select = "c.start_date::date AS start_date," if has_start_date else "NULL::date AS start_date,"
        has_status = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'status'
            )
        """)).scalar()
        has_deleted_at = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'deleted_at'
            )
        """)).scalar()
        status_select = "c.status" if has_status else "'DONE'"
        has_visibility = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'visibility'
            )
        """)).scalar()
        visibility_select = "c.visibility" if has_visibility else "'PRIVATE'"
        deleted_filter = "AND c.deleted_at IS NULL" if has_deleted_at else ""
        sql = text(f"""
            SELECT c.course_id, c.title, c.departure_station, c.total_days, {status_select} AS status,
                   {visibility_select} AS visibility, {start_date_select}
                   c.created_at, cb.created_at AS saved_at
            FROM oneulro.course_bookmark cb
            JOIN oneulro.course c ON c.course_id = cb.course_id
            WHERE cb.user_id = :user_id
              {deleted_filter}
            ORDER BY cb.created_at DESC
        """)
        rows = conn.execute(sql, {"user_id": user_id}).mappings().all()
    return [dict(r) for r in rows]


def get_created_courses(user_id: int) -> list[dict]:
    """내가 생성한 코스를 최신순으로 조회한다."""
    if engine is None:
        return []

    with engine.connect() as conn:
        has_start_date = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'start_date'
            )
        """)).scalar()
        has_status = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'status'
            )
        """)).scalar()
        has_deleted_at = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'deleted_at'
            )
        """)).scalar()

        start_date_select = "c.start_date::date" if has_start_date else "NULL::date"
        end_date_select = "c.end_date::date" if "end_date" in {
            row[0]
            for row in conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
            """)).all()
        } else "NULL::date"
        status_select = "c.status" if has_status else "'DONE'"
        visibility_select = "c.visibility" if conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'visibility'
            )
        """)).scalar() else "'PRIVATE'"
        deleted_filter = "AND c.deleted_at IS NULL" if has_deleted_at else ""
        rows = conn.execute(text(f"""
            SELECT c.course_id, c.title, c.departure_station, c.total_days,
                   {status_select} AS status,
                   {visibility_select} AS visibility,
                   {start_date_select} AS start_date,
                   {end_date_select} AS end_date,
                   c.created_at,
                   c.created_at AS saved_at
            FROM oneulro.course c
            WHERE c.user_id = :user_id
              {deleted_filter}
            ORDER BY c.created_at DESC
        """), {"user_id": user_id}).mappings().all()

    return [dict(row) for row in rows]


def get_liked_courses(user_id: int) -> list[dict]:
    """사용자가 좋아요를 누른 공개 코스를 최신 좋아요순으로 조회한다."""
    if engine is None:
        return []

    with engine.connect() as conn:
        has_course_like = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course_like'
            )
        """)).scalar()
        if not has_course_like:
            raise HTTPException(status_code=501, detail="course_like 테이블이 필요합니다")

        columns = {
            row[0]
            for row in conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
            """)).all()
        }
        start_date_select = "c.start_date::date" if "start_date" in columns else "NULL::date"
        status_select = "c.status" if "status" in columns else "'DONE'"
        visibility_select = "c.visibility" if "visibility" in columns else "'PRIVATE'"
        visibility_filter = "AND c.visibility = 'PUBLIC'" if "visibility" in columns else ""
        deleted_filter = "AND c.deleted_at IS NULL" if "deleted_at" in columns else ""

        rows = conn.execute(text(f"""
            SELECT c.course_id, c.title, c.departure_station, c.total_days,
                   {status_select} AS status,
                   {visibility_select} AS visibility,
                   {start_date_select} AS start_date,
                   c.created_at,
                   cl.created_at AS saved_at
            FROM oneulro.course_like cl
            JOIN oneulro.course c ON c.course_id = cl.course_id
            WHERE cl.user_id = :user_id
              {visibility_filter}
              {deleted_filter}
            ORDER BY cl.created_at DESC
        """), {"user_id": user_id}).mappings().all()

    return [dict(row) for row in rows]


def delete_created_course(user_id: int, course_id: int) -> None:
    """소유자의 코스를 soft delete한다."""
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.begin() as conn:
        columns = {
            row[0]
            for row in conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
            """)).all()
        }
        if "deleted_at" not in columns:
            raise HTTPException(status_code=501, detail="코스 삭제를 위한 deleted_at 컬럼이 필요합니다")

        updated_at_sql = ", updated_at = NOW()" if "updated_at" in columns else ""
        result = conn.execute(text(f"""
            UPDATE oneulro.course
            SET deleted_at = NOW(){updated_at_sql}
            WHERE course_id = :course_id
              AND user_id = :user_id
              AND deleted_at IS NULL
        """), {"course_id": course_id, "user_id": user_id})

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="삭제할 코스를 찾을 수 없습니다")


def update_course_visibility(user_id: int, course_id: int, visibility: str) -> dict:
    """소유자의 코스 공개 상태를 변경한다."""
    if visibility not in {"PUBLIC", "PRIVATE"}:
        raise HTTPException(status_code=422, detail="올바른 공개 상태가 아닙니다")
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.begin() as conn:
        columns = {
            row[0]
            for row in conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
            """)).all()
        }
        if "visibility" not in columns:
            raise HTTPException(status_code=501, detail="course.visibility 컬럼이 필요합니다")

        deleted_filter = "AND deleted_at IS NULL" if "deleted_at" in columns else ""
        updated_at_sql = ", updated_at = NOW()" if "updated_at" in columns else ""
        row = conn.execute(text(f"""
            UPDATE oneulro.course
            SET visibility = :visibility{updated_at_sql}
            WHERE course_id = :course_id
              AND user_id = :user_id
              {deleted_filter}
            RETURNING course_id, visibility
        """), {
            "course_id": course_id,
            "user_id": user_id,
            "visibility": visibility,
        }).mappings().one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="변경할 코스를 찾을 수 없습니다")
    return dict(row)


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
