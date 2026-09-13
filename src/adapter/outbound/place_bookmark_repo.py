from fastapi import HTTPException
from sqlalchemy import text

from src.db import engine


def attach_internal_places(attractions: list[dict], user_id: int | None = None) -> list[dict]:
    """관광공사 결과를 이미 저장된 코스 장소와 연결한다.

    장소명이 같고 좌표가 약 150m 이내인 가장 최근 레코드를 사용한다.
    """
    if engine is None or not attractions:
        return attractions

    names = [item.get("title") for item in attractions if item.get("title")]
    if not names:
        return attractions

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT ON (p.name)
                   p.place_id, p.name, p.lat, p.lng,
                   CASE WHEN pb.place_id IS NULL THEN FALSE ELSE TRUE END AS bookmarked
            FROM oneulro.place p
            LEFT JOIN oneulro.place_bookmark pb
              ON pb.place_id = p.place_id AND pb.user_id = :user_id
            WHERE p.name = ANY(:names)
            ORDER BY p.name, p.updated_at DESC, p.place_id DESC
        """), {"names": names, "user_id": user_id or -1}).mappings().all()

    candidates = {row["name"]: row for row in rows}
    linked: list[dict] = []
    for attraction in attractions:
        candidate = candidates.get(attraction.get("title"))
        if candidate and attraction.get("mapx") and attraction.get("mapy"):
            close_enough = (
                abs(float(candidate["lng"]) - float(attraction["mapx"])) <= 0.0015
                and abs(float(candidate["lat"]) - float(attraction["mapy"])) <= 0.0015
            )
        else:
            close_enough = candidate is not None
        linked.append({
            **attraction,
            "place_id": candidate["place_id"] if candidate and close_enough else None,
            "bookmarked": bool(candidate["bookmarked"]) if candidate and close_enough else False,
        })
    return linked


def _ensure_place_exists(conn, place_id: int) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM oneulro.place WHERE place_id = :place_id"),
        {"place_id": place_id},
    ).one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다")


def list_place_bookmarks(user_id: int) -> list[dict]:
    if engine is None:
        return []

    with engine.connect() as conn:
        has_course_deleted_at = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'oneulro'
                  AND table_name = 'course'
                  AND column_name = 'deleted_at'
            )
        """)).scalar()
        deleted_filter = "AND c.deleted_at IS NULL" if has_course_deleted_at else ""

        rows = conn.execute(text(f"""
            SELECT
                p.place_id,
                p.name,
                p.category,
                p.address,
                p.lat,
                p.lng,
                p.image_url,
                p.opening_hours,
                p.walk_minutes,
                p.congestion_score,
                p.weather_summary,
                p.pet_allowed,
                p.indoor_yn,
                p.free_yn,
                cs.station_name,
                c.course_id,
                c.title AS course_title,
                pb.created_at AS bookmarked_at
            FROM oneulro.place_bookmark pb
            JOIN oneulro.place p ON p.place_id = pb.place_id
            LEFT JOIN oneulro.course_stop cs ON cs.stop_id = p.stop_id
            LEFT JOIN oneulro.course c ON c.course_id = cs.course_id
            WHERE pb.user_id = :user_id
              {deleted_filter}
            ORDER BY pb.created_at DESC
        """), {"user_id": user_id}).mappings().all()

    return [dict(row) for row in rows]


def is_place_bookmarked(user_id: int, place_id: int) -> bool:
    if engine is None:
        return False

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT 1
            FROM oneulro.place_bookmark
            WHERE user_id = :user_id
              AND place_id = :place_id
        """), {"user_id": user_id, "place_id": place_id}).one_or_none()
    return row is not None


def toggle_place_bookmark(user_id: int, place_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.connect() as conn:
        _ensure_place_exists(conn, place_id)
        deleted = conn.execute(text("""
            DELETE FROM oneulro.place_bookmark
            WHERE user_id = :user_id
              AND place_id = :place_id
        """), {"user_id": user_id, "place_id": place_id})

        bookmarked = deleted.rowcount == 0
        if bookmarked:
            conn.execute(text("""
                INSERT INTO oneulro.place_bookmark (user_id, place_id)
                VALUES (:user_id, :place_id)
                ON CONFLICT (user_id, place_id) DO NOTHING
            """), {"user_id": user_id, "place_id": place_id})

        conn.commit()

    return {"place_id": place_id, "bookmarked": bookmarked}
