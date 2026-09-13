from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text

from src.db import engine


def _validate_linked_course(conn, user_id: int, course_id: Optional[int]) -> None:
    if course_id is None:
        return
    course = conn.execute(text("""
        SELECT 1 FROM oneulro.course
        WHERE course_id = :course_id AND user_id = :user_id AND deleted_at IS NULL
    """), {"course_id": course_id, "user_id": user_id}).one_or_none()
    if not course:
        raise HTTPException(status_code=422, detail="연결할 수 없는 코스입니다")


def list_posts(user_id: Optional[int] = None) -> list[dict]:
    if engine is None:
        return []
    owner_filter = "AND p.user_id = :user_id" if user_id is not None else ""
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT p.post_id, p.user_id, p.course_id, p.title, p.content,
                   p.created_at, p.updated_at, u.nickname AS author_nickname
            FROM oneulro.community_post p
            JOIN oneulro.app_user u ON u.user_id = p.user_id
            WHERE p.deleted_at IS NULL {owner_filter}
            ORDER BY p.created_at DESC
        """), {"user_id": user_id}).mappings().all()
    return [dict(row) for row in rows]


def get_post(post_id: int) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT p.post_id, p.user_id, p.course_id, p.title, p.content,
                   p.created_at, p.updated_at, u.nickname AS author_nickname
            FROM oneulro.community_post p
            JOIN oneulro.app_user u ON u.user_id = p.user_id
            WHERE p.post_id = :post_id AND p.deleted_at IS NULL
        """), {"post_id": post_id}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")
    return dict(row)


def create_post(user_id: int, title: str, content: str, course_id: Optional[int]) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        _validate_linked_course(conn, user_id, course_id)
        row = conn.execute(text("""
            INSERT INTO oneulro.community_post (user_id, course_id, title, content)
            VALUES (:user_id, :course_id, :title, :content)
            RETURNING post_id, user_id, course_id, title, content, created_at, updated_at
        """), {"user_id": user_id, "course_id": course_id, "title": title, "content": content}).mappings().one()
    return dict(row)


def update_post(user_id: int, post_id: int, title: str, content: str, course_id: Optional[int]) -> dict:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        _validate_linked_course(conn, user_id, course_id)
        row = conn.execute(text("""
            UPDATE oneulro.community_post
            SET title = :title, content = :content, course_id = :course_id, updated_at = NOW()
            WHERE post_id = :post_id AND user_id = :user_id AND deleted_at IS NULL
            RETURNING post_id, user_id, course_id, title, content, created_at, updated_at
        """), {"post_id": post_id, "user_id": user_id, "course_id": course_id, "title": title, "content": content}).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="수정할 게시글을 찾을 수 없습니다")
    return dict(row)


def delete_post(user_id: int, post_id: int) -> None:
    if engine is None:
        raise HTTPException(status_code=503, detail="DB 연결 없음")
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE oneulro.community_post SET deleted_at = NOW(), updated_at = NOW()
            WHERE post_id = :post_id AND user_id = :user_id AND deleted_at IS NULL
        """), {"post_id": post_id, "user_id": user_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="삭제할 게시글을 찾을 수 없습니다")
