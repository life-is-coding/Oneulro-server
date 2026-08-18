import asyncio
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.repositories.course_repo import (
    add_place,
    bookmark_course,
    create_course,
    delete_place,
    get_course_detail,
    get_course_stops,
    list_bookmarked_courses,
    replace_all_places,
    replace_stop_places,
    unbookmark_course,
    update_alias,
)
from src.services.course_narrative import generate_reason, generate_title
from src.services.tourism_api import fetch_nearby_attractions

router = APIRouter(prefix="/courses", tags=["courses"])

# 재생성 시 조회할 장소 카테고리 (관광지/식당/숙박/쇼핑)
_REGEN_CONTENT_TYPE_IDS = [12, 39, 32, 38]


class PlaceItem(BaseModel):
    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    image_url: Optional[str] = None
    opening_hours: Optional[str] = None
    walk_minutes: Optional[int] = None
    congestion_score: Optional[int] = None
    weather_summary: Optional[str] = None
    pet_allowed: bool = False
    indoor_yn: bool = False
    free_yn: bool = False


class StopItem(BaseModel):
    day_number: int = 1
    sequence: int = 1
    station_name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    image_url: Optional[str] = None
    congestion_score: Optional[int] = None
    is_benefit_station: bool = False
    travel_minutes: Optional[int] = None
    train_type: Optional[str] = None
    train_number: Optional[str] = None
    seat_class: Optional[str] = None
    arrive_at: Optional[str] = None
    depart_at: Optional[str] = None
    stay_minutes: Optional[int] = None
    places: list[PlaceItem] = []


class CreateCourseRequest(BaseModel):
    title: Optional[str] = None
    alias: Optional[str] = None
    departure_station: str
    total_days: int
    preset_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    recommendation_reason: Optional[str] = None
    stops: list[StopItem]

    # title/recommendation_reason 자동생성에만 쓰이는 조건 (저장 안 됨)
    theme_tags: Optional[list[str]] = None
    companion_type: Optional[str] = None
    pet_mode: Optional[str] = None
    natural_language_memo: Optional[str] = None


class UpdateAliasRequest(BaseModel):
    alias: str


class AddPlaceRequest(PlaceItem):
    stop_id: int


@router.post("")
def create(body: CreateCourseRequest, user=Depends(get_current_user)):
    """추천 코스를 DB에 저장하고 course_id 반환. 제목/선정이유 미입력 시 자동 생성."""
    title = body.title or generate_title(
        destinations=[s.station_name for s in body.stops],
        total_days=body.total_days,
        theme_tags=body.theme_tags,
    )
    reason = body.recommendation_reason or generate_reason(
        companion_type=body.companion_type,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        pet_mode=body.pet_mode,
        theme_tags=body.theme_tags,
        natural_language_memo=body.natural_language_memo,
    )

    course_id = create_course(
        user_id=int(user["sub"]),
        title=title,
        alias=body.alias,
        departure_station=body.departure_station,
        total_days=body.total_days,
        recommendation_reason=reason,
        stops=[s.model_dump() for s in body.stops],
        preset_id=body.preset_id,
        start_date=body.start_date,
        end_date=body.end_date,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
    )
    return {"course_id": course_id, "title": title, "recommendation_reason": reason}


@router.get("/saved")
def list_saved_courses(user=Depends(get_current_user)):
    """저장(북마크)한 코스 목록 조회"""
    return list_bookmarked_courses(int(user["sub"]))


@router.get("/{course_id}")
def course_detail(course_id: int, user=Depends(get_current_user)):
    """코스 결과 화면용 상세 조회 — 역별 그룹핑된 장소 포함"""
    detail = get_course_detail(course_id, int(user["sub"]))
    if not detail:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다")
    return detail


@router.patch("/{course_id}")
def update_course_alias(course_id: int, body: UpdateAliasRequest, user=Depends(get_current_user)):
    """코스 별칭 수정"""
    return update_alias(course_id, int(user["sub"]), body.alias)


@router.post("/{course_id}/save")
def save(course_id: int, user=Depends(get_current_user)):
    """코스 저장(북마크)"""
    return bookmark_course(int(user["sub"]), course_id)


@router.delete("/{course_id}/save")
def unsave(course_id: int, user=Depends(get_current_user)):
    """코스 저장 취소"""
    unbookmark_course(int(user["sub"]), course_id)
    return {"message": "저장이 취소되었습니다"}


@router.post("/{course_id}/places")
def create_place(course_id: int, body: AddPlaceRequest, user=Depends(get_current_user)):
    """코스의 특정 역에 장소 추가"""
    data = body.model_dump(exclude={"stop_id"})
    return add_place(course_id, int(user["sub"]), body.stop_id, data)


@router.delete("/{course_id}/places/{place_id}")
def remove_place(course_id: int, place_id: int, user=Depends(get_current_user)):
    """코스에서 장소 삭제"""
    delete_place(course_id, int(user["sub"]), place_id)
    return {"message": "장소가 삭제되었습니다"}


async def _fetch_places_for_stop(lat: float, lng: float) -> list[dict]:
    try:
        attraction_lists = await asyncio.gather(
            *[
                fetch_nearby_attractions(map_x=lng, map_y=lat, radius=5000, content_type_id=ctid, num_of_rows=5)
                for ctid in _REGEN_CONTENT_TYPE_IDS
            ]
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"관광공사 API 호출 실패: {str(e)}")

    places = []
    for attractions in attraction_lists:
        for item in attractions:
            places.append({
                "name": item.get("title", ""),
                "category": item.get("category"),
                "address": item.get("addr"),
                "lat": item.get("mapy"),
                "lng": item.get("mapx"),
                "image_url": item.get("image"),
            })
    return places


@router.post("/{course_id}/regenerate")
async def regenerate_course(course_id: int, user=Depends(get_current_user)):
    """코스 전체 재생성 — 각 역 주변 장소를 다시 조회해 교체"""
    stops = get_course_stops(course_id, int(user["sub"]))
    stops_with_coords = [s for s in stops if s["lat"] is not None and s["lng"] is not None]

    places_lists = await asyncio.gather(
        *[_fetch_places_for_stop(float(s["lat"]), float(s["lng"])) for s in stops_with_coords]
    )
    places_by_stop = {s["stop_id"]: places for s, places in zip(stops_with_coords, places_lists)}

    replace_all_places(course_id, int(user["sub"]), places_by_stop)
    return get_course_detail(course_id, int(user["sub"]))


@router.post("/{course_id}/stops/{stop_id}/regenerate")
async def regenerate_stop(course_id: int, stop_id: int, user=Depends(get_current_user)):
    """코스의 특정 역만 재생성"""
    stops = get_course_stops(course_id, int(user["sub"]))
    stop = next((s for s in stops if s["stop_id"] == stop_id), None)
    if not stop:
        raise HTTPException(status_code=404, detail="해당 코스에 속한 역이 아닙니다")
    if stop["lat"] is None or stop["lng"] is None:
        raise HTTPException(status_code=400, detail="역의 좌표 정보가 없어 재생성할 수 없습니다")

    places = await _fetch_places_for_stop(float(stop["lat"]), float(stop["lng"]))
    return {"stop_id": stop_id, "places": replace_stop_places(course_id, int(user["sub"]), stop_id, places)}
