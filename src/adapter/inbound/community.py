from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.adapter.outbound.community_repo import (
    get_community_course,
    list_best_community_courses,
    list_community_courses,
    rate_course,
    toggle_course_like,
)
from src.core.config import get_settings
from src.core.dependencies import get_current_user
from src.application.session import get_redis_session

router = APIRouter(prefix="/community", tags=["community"])


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)


def get_optional_user_id(request: Request) -> Optional[int]:
    session_id = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    if not session_id:
        return None
    try:
        return int(get_redis_session(session_id)["sub"])
    except Exception:
        return None


@router.get("/courses")
def community_courses(request: Request, sort: Literal["latest", "rating", "likes", "views"] = "latest", theme: Optional[str] = None):
    """커뮤니티 코스 목록 조회"""
    return list_community_courses(sort, get_optional_user_id(request), theme)


@router.get("/courses/best")
def best_community_courses(request: Request, sort: Literal["rating", "likes", "views"] = "rating"):
    """커뮤니티 BEST 10 조회"""
    return list_best_community_courses(sort, get_optional_user_id(request), limit=10)


@router.get("/courses/{course_id}")
def community_course_detail(course_id: int, request: Request):
    """커뮤니티 코스 상세 조회. 상세 진입 시 조회수를 1 증가시킨다."""
    return get_community_course(course_id, get_optional_user_id(request))


@router.post("/courses/{course_id}/like")
def like_community_course(course_id: int, user=Depends(get_current_user)):
    """커뮤니티 코스 좋아요 토글"""
    return toggle_course_like(course_id, int(user["sub"]))


@router.put("/courses/{course_id}/rating")
def rate_community_course(course_id: int, body: RatingRequest, user=Depends(get_current_user)):
    """커뮤니티 코스 별점 저장/수정"""
    return rate_course(course_id, int(user["sub"]), body.rating)
