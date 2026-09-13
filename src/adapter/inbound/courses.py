from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.core.logging import logger
from src.adapter.outbound.course_repo import (
    create_course,
    delete_created_course,
    get_course_detail,
    get_created_courses,
    get_liked_courses,
    get_saved_courses,
    save_course,
    unsave_course,
    update_course_visibility,
)
from src.adapter.outbound.notification_repo import create_notification

router = APIRouter(prefix="/courses", tags=["courses"])


class AttractionItem(BaseModel):
    contentid: Optional[str] = None
    title: str
    addr: Optional[str] = None
    image: Optional[str] = None
    category: Optional[str] = None
    mapx: Optional[str] = None
    mapy: Optional[str] = None
    area_cd: Optional[str] = None
    signgu_cd: Optional[str] = None


class DayItem(BaseModel):
    day: Optional[int] = None
    day_number: Optional[int] = None
    city: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    attractions: list[AttractionItem] = []


class CreateCourseRequest(BaseModel):
    title: str
    departure_station: str
    total_days: int
    theme_tags: list[str] = Field(default_factory=list)
    days: list[DayItem]


class UpdateCourseVisibilityRequest(BaseModel):
    visibility: Literal["PUBLIC", "PRIVATE"]


@router.post("")
def create(body: CreateCourseRequest, user=Depends(get_current_user)):
    """추천 코스를 DB에 저장하고 course_id 반환"""
    course_id = create_course(
        user_id=int(user["sub"]),
        title=body.title,
        departure_station=body.departure_station,
        total_days=body.total_days,
        theme_tags=body.theme_tags,
        days=[d.model_dump() for d in body.days],
    )
    create_notification(
        int(user["sub"]), "travel", "새 여행 코스가 완성됐어요",
        body.title, "owned_course", course_id, f"course:{course_id}:created",
    )
    return {"course_id": course_id}


@router.get("/saved")
def list_saved_courses(user=Depends(get_current_user)):
    """저장한 코스 목록 조회"""
    return get_saved_courses(int(user["sub"]))


@router.get("/mine")
def list_created_courses(user=Depends(get_current_user)):
    """내가 생성한 코스 목록 조회"""
    return get_created_courses(int(user["sub"]))


@router.get("/liked")
def list_liked_courses(user=Depends(get_current_user)):
    """내가 좋아요를 누른 코스 목록 조회"""
    return get_liked_courses(int(user["sub"]))


@router.get("/{course_id}")
def course_detail(course_id: int, user=Depends(get_current_user)):
    """코스 상세 조회 — 경유역 및 장소 포함"""
    logger.info(f"코스결과 조회: course_id={course_id}, user_id={user['sub']}")
    detail = get_course_detail(course_id)
    if not detail:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
    is_owner = int(detail["user_id"]) == int(user["sub"])
    if detail.get("visibility", "PRIVATE") != "PUBLIC" and not is_owner:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
    return {
        **detail,
        "is_owner": is_owner,
    }


@router.patch("/{course_id}/visibility")
def change_course_visibility(
    course_id: int,
    body: UpdateCourseVisibilityRequest,
    user=Depends(get_current_user),
):
    """내가 생성한 코스의 공개/비공개 상태 변경"""
    return update_course_visibility(int(user["sub"]), course_id, body.visibility)


@router.post("/{course_id}/save")
def save(course_id: int, user=Depends(get_current_user)):
    """코스 저장"""
    return save_course(int(user["sub"]), course_id)


@router.delete("/{course_id}/save")
def unsave(course_id: int, user=Depends(get_current_user)):
    """코스 저장 취소"""
    unsave_course(int(user["sub"]), course_id)
    return {"message": "저장이 취소되었습니다"}


@router.delete("/{course_id}")
def delete_owned_course(course_id: int, user=Depends(get_current_user)):
    """내가 생성한 코스 삭제"""
    delete_created_course(int(user["sub"]), course_id)
    return {"message": "코스가 삭제되었습니다"}
