from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from src.adapter.outbound.place_bookmark_repo import (
    is_place_bookmarked,
    list_place_bookmarks,
    toggle_place_bookmark,
)
from src.adapter.outbound.course_repo import get_place
from src.adapter.outbound.tourism_api import fetch_congestion_trend
from src.application.session import get_redis_session
from src.core.config import get_settings
from src.core.dependencies import get_current_user
from src.core.logging import logger

router = APIRouter(prefix="/places", tags=["places"])


def get_optional_user_id(request: Request) -> Optional[int]:
    session_id = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    if not session_id:
        return None
    try:
        return int(get_redis_session(session_id)["sub"])
    except Exception:
        return None


@router.get("/bookmarks")
def my_place_bookmarks(user=Depends(get_current_user)):
    """내가 찜한 장소 목록 조회"""
    return list_place_bookmarks(int(user["sub"]))


@router.get("/{place_id}")
async def place_detail(place_id: int, request: Request):
    """장소 상세 조회 — 관광공사 집중률 API로 방문자 추이(혼잡도)를 함께 내려준다."""
    place = get_place(place_id)
    if not place:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다")

    congestion_trend: list[dict] = []
    if place.get("area_cd") and place.get("signgu_cd"):
        try:
            congestion_trend = await fetch_congestion_trend(
                area_cd=place["area_cd"],
                signgu_cd=place["signgu_cd"],
                place_name=place["name"],
            )
        except Exception as e:
            # 이 관광지가 집중률 큐레이션 대상이 아니거나 API 오류인 경우 — 방문자 추이 없이 나머지 정보는 정상 제공
            logger.warning(f"방문자 추이 조회 실패: place_id={place_id} error={e}")

    today = date.today().strftime("%Y%m%d")
    today_row = next((row for row in congestion_trend if row["date"] == today), None)

    place["congestion_trend"] = congestion_trend
    place["congestion_score"] = round(today_row["rate"]) if today_row else place.get("congestion_score")
    user_id = get_optional_user_id(request)
    place["bookmarked"] = is_place_bookmarked(user_id, place_id) if user_id else False

    return place


@router.get("/{place_id}/bookmark")
def place_bookmark_status(place_id: int, user=Depends(get_current_user)):
    """장소 찜 여부 조회"""
    return {"place_id": place_id, "bookmarked": is_place_bookmarked(int(user["sub"]), place_id)}


@router.post("/{place_id}/bookmark")
def toggle_bookmark_place(place_id: int, user=Depends(get_current_user)):
    """장소 찜 토글"""
    return toggle_place_bookmark(int(user["sub"]), place_id)
