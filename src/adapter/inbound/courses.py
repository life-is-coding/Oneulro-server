from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.core.dependencies import get_current_user
from src.adapter.outbound.course_repo import get_saved_courses, save_course, unsave_course, get_course_detail, create_course

router = APIRouter(prefix="/courses", tags=["courses"])


class AttractionItem(BaseModel):
    contentid: Optional[str] = None
    title: str
    addr: Optional[str] = None
    image: Optional[str] = None
    category: Optional[str] = None
    mapx: Optional[str] = None
    mapy: Optional[str] = None


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
    days: list[DayItem]


@router.post("")
def create(body: CreateCourseRequest, user=Depends(get_current_user)):
    """추천 코스를 DB에 저장하고 course_id 반환"""
    course_id = create_course(
        user_id=int(user["sub"]),
        title=body.title,
        departure_station=body.departure_station,
        total_days=body.total_days,
        days=[d.model_dump() for d in body.days],
    )
    return {"course_id": course_id}


@router.get("/saved")
def list_saved_courses(user=Depends(get_current_user)):
    """저장한 코스 목록 조회"""
    return get_saved_courses(int(user["sub"]))


@router.get("/{course_id}")
def course_detail(course_id: int, user=Depends(get_current_user)):
    """코스 상세 조회 — 경유역 및 장소 포함"""
    detail = get_course_detail(course_id)
    if not detail:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
    return detail


@router.post("/{course_id}/save")
def save(course_id: int, user=Depends(get_current_user)):
    """코스 저장"""
    return save_course(int(user["sub"]), course_id)


@router.delete("/{course_id}/save")
def unsave(course_id: int, user=Depends(get_current_user)):
    """코스 저장 취소"""
    unsave_course(int(user["sub"]), course_id)
    return {"message": "저장이 취소되었습니다"}
