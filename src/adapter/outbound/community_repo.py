from typing import Literal, Optional

from fastapi import HTTPException
from sqlalchemy import text

from src.adapter.outbound.course_repo import get_course_detail
from src.db import engine

CommunitySort = Literal["latest", "rating", "likes", "views"]


def _table_exists(conn, table_name: str) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'oneulro'
              AND table_name = :table_name
        )
    """), {"table_name": table_name}).scalar())


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'oneulro'
              AND table_name = :table_name
              AND column_name = :column_name
        )
    """), {"table_name": table_name, "column_name": column_name}).scalar())


def _author_sql(conn) -> tuple[str, str]:
    if _table_exists(conn, "app_user"):
        return (
            "LEFT JOIN oneulro.app_user u ON u.user_id = c.user_id",
            "COALESCE(u.nickname, '오늘로 여행자') AS author_nickname, u.profile_image_url AS author_profile_image_url",
        )

    return (
        "LEFT JOIN oneulro.users u ON u.user_id = c.user_id",
        "COALESCE(u.nickname, '오늘로 여행자') AS author_nickname, u.profile_image_url AS author_profile_image_url",
    )


def _community_capabilities(conn) -> dict[str, bool]:
    return {
        "has_status": _column_exists(conn, "course", "status"),
        "has_visibility": _column_exists(conn, "course", "visibility"),
        "has_view_count": _column_exists(conn, "course", "view_count"),
        "has_deleted_at": _column_exists(conn, "course", "deleted_at"),
        "has_course_like": _table_exists(conn, "course_like"),
        "has_course_rating": _table_exists(conn, "course_rating"),
    }


def _course_select_sql(conn, viewer_user_id: Optional[int], sort: CommunitySort, where_clause: str = "", limit_clause: str = ""):
    author_join, author_select = _author_sql(conn)
    caps = _community_capabilities(conn)

    status_select = "c.status" if caps["has_status"] else "'DONE'"
    view_count_select = "c.view_count" if caps["has_view_count"] else "0"

    like_join = """
        LEFT JOIN (
            SELECT course_id, COUNT(*)::INTEGER AS like_count
            FROM oneulro.course_like
            GROUP BY course_id
        ) l ON l.course_id = c.course_id
    """ if caps["has_course_like"] else ""
    like_count_select = "COALESCE(l.like_count, 0)" if caps["has_course_like"] else "0"

    rating_join = """
        LEFT JOIN (
            SELECT course_id,
                   COUNT(*)::INTEGER AS rating_count,
                   ROUND(AVG(rating)::numeric, 1)::float AS average_rating
            FROM oneulro.course_rating
            GROUP BY course_id
        ) r ON r.course_id = c.course_id
    """ if caps["has_course_rating"] else ""
    rating_count_select = "COALESCE(r.rating_count, 0)" if caps["has_course_rating"] else "0"
    average_rating_select = "COALESCE(r.average_rating, 0)" if caps["has_course_rating"] else "0"

    where_parts = []
    if caps["has_status"]:
        where_parts.append("c.status = 'DONE'")
    if caps["has_visibility"]:
        where_parts.append("c.visibility = 'PUBLIC'")
    if caps["has_deleted_at"]:
        where_parts.append("c.deleted_at IS NULL")
    if viewer_user_id is not None:
        where_parts.append("c.user_id != :viewer_user_id")
    if where_clause:
        where_parts.append(where_clause)
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    sort_sql = {
        "latest": "c.created_at DESC",
        "rating": "average_rating DESC NULLS LAST, like_count DESC, view_count DESC, c.created_at DESC",
        "likes": "like_count DESC, average_rating DESC NULLS LAST, view_count DESC, c.created_at DESC",
        "views": "view_count DESC, like_count DESC, average_rating DESC NULLS LAST, c.created_at DESC",
    }.get(sort, "c.created_at DESC")

    return text(f"""
        SELECT
            c.course_id,
            c.user_id,
            c.title,
            c.departure_station,
            c.total_days,
            {status_select} AS status,
            c.created_at,
            {author_select},
            {view_count_select} AS view_count,
            {like_count_select} AS like_count,
            {rating_count_select} AS rating_count,
            {average_rating_select} AS average_rating,
            first_place.image_url AS image_url
        FROM oneulro.course c
        {author_join}
        {like_join}
        {rating_join}
        LEFT JOIN LATERAL (
            SELECT p.image_url
            FROM oneulro.course_stop cs
            JOIN oneulro.place p ON p.stop_id = cs.stop_id
            WHERE cs.course_id = c.course_id
              AND NULLIF(p.image_url, '') IS NOT NULL
            ORDER BY cs.day_number, cs.sequence, p.place_id
            LIMIT 1
        ) first_place ON true
        {where_sql}
        ORDER BY {sort_sql}
        {limit_clause}
    """)


def list_community_courses(sort: CommunitySort = "latest", viewer_user_id: Optional[int] = None) -> list[dict]:
    if engine is None:
        return []

    with engine.connect() as conn:
        rows = conn.execute(
            _course_select_sql(conn, viewer_user_id, sort),
            {"viewer_user_id": viewer_user_id},
        ).mappings().all()

    return [dict(row) for row in rows]


def list_best_community_courses(sort: Literal["rating", "likes", "views"] = "rating", viewer_user_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    if engine is None:
        return []

    with engine.connect() as conn:
        rows = conn.execute(
            _course_select_sql(conn, viewer_user_id, sort, limit_clause="LIMIT :limit"),
            {"viewer_user_id": viewer_user_id, "limit": max(1, min(limit, 50))},
        ).mappings().all()

    return [dict(row) for row in rows]


def get_community_course(course_id: int, viewer_user_id: Optional[int] = None) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.begin() as conn:
        caps = _community_capabilities(conn)

        if caps["has_view_count"]:
            update_sql = """
                UPDATE oneulro.course
                SET view_count = view_count + 1,
                    updated_at = NOW()
                WHERE course_id = :course_id
            """ if _column_exists(conn, "course", "updated_at") else """
                UPDATE oneulro.course
                SET view_count = view_count + 1
                WHERE course_id = :course_id
            """
            conn.execute(text(update_sql), {"course_id": course_id})

        row = conn.execute(
            _course_select_sql(conn, viewer_user_id=None, sort="latest", where_clause="c.course_id = :course_id", limit_clause="LIMIT 1"),
            {"course_id": course_id},
        ).mappings().one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")

        liked = False
        my_rating = None
        if viewer_user_id is not None and caps["has_course_like"]:
            liked = bool(conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM oneulro.course_like
                    WHERE course_id = :course_id
                      AND user_id = :user_id
                )
            """), {"course_id": course_id, "user_id": viewer_user_id}).scalar())
        if viewer_user_id is not None and caps["has_course_rating"]:
            my_rating = conn.execute(text("""
                SELECT rating
                FROM oneulro.course_rating
                WHERE course_id = :course_id
                  AND user_id = :user_id
            """), {"course_id": course_id, "user_id": viewer_user_id}).scalar()

    detail = get_course_detail(course_id)
    if not detail:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")

    return {
        **dict(row),
        "liked": liked,
        "my_rating": my_rating,
        "detail": detail,
    }


def toggle_course_like(course_id: int, user_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.begin() as conn:
        if not _table_exists(conn, "course_like"):
            raise HTTPException(status_code=501, detail="course_like 테이블이 필요합니다")

        exists_sql = """
            SELECT EXISTS (
                SELECT 1
                FROM oneulro.course
                WHERE course_id = :course_id
                  AND visibility = 'PUBLIC'
            )
        """ if _column_exists(conn, "course", "visibility") else """
            SELECT EXISTS (
                SELECT 1
                FROM oneulro.course
                WHERE course_id = :course_id
            )
        """
        exists = conn.execute(text(exists_sql), {"course_id": course_id}).scalar()
        if not exists:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")

        deleted = conn.execute(text("""
            DELETE FROM oneulro.course_like
            WHERE user_id = :user_id
              AND course_id = :course_id
        """), {"user_id": user_id, "course_id": course_id})

        liked = deleted.rowcount == 0
        if liked:
            conn.execute(text("""
                INSERT INTO oneulro.course_like (user_id, course_id)
                VALUES (:user_id, :course_id)
                ON CONFLICT (user_id, course_id) DO NOTHING
            """), {"user_id": user_id, "course_id": course_id})

        like_count = conn.execute(text("""
            SELECT COUNT(*)::INTEGER
            FROM oneulro.course_like
            WHERE course_id = :course_id
        """), {"course_id": course_id}).scalar()

    return {"liked": liked, "like_count": like_count}


def rate_course(course_id: int, user_id: int, rating: int) -> dict:
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=422, detail="별점은 1~5점만 가능합니다")
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")

    with engine.begin() as conn:
        if not _table_exists(conn, "course_rating"):
            raise HTTPException(status_code=501, detail="course_rating 테이블이 필요합니다")

        exists_sql = """
            SELECT EXISTS (
                SELECT 1
                FROM oneulro.course
                WHERE course_id = :course_id
                  AND visibility = 'PUBLIC'
            )
        """ if _column_exists(conn, "course", "visibility") else """
            SELECT EXISTS (
                SELECT 1
                FROM oneulro.course
                WHERE course_id = :course_id
            )
        """
        exists = conn.execute(text(exists_sql), {"course_id": course_id}).scalar()
        if not exists:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")

        conn.execute(text("""
            INSERT INTO oneulro.course_rating (user_id, course_id, rating)
            VALUES (:user_id, :course_id, :rating)
            ON CONFLICT (user_id, course_id)
            DO UPDATE SET rating = EXCLUDED.rating,
                          updated_at = NOW()
        """), {"user_id": user_id, "course_id": course_id, "rating": rating})

        stats = conn.execute(text("""
            SELECT COUNT(*)::INTEGER AS rating_count,
                   ROUND(AVG(rating)::numeric, 1)::float AS average_rating
            FROM oneulro.course_rating
            WHERE course_id = :course_id
        """), {"course_id": course_id}).mappings().one()

    return {"my_rating": rating, **dict(stats)}
