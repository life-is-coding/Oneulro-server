from datetime import date

from fastapi import APIRouter, HTTPException

from src.adapter.outbound.course_repo import get_place
from src.adapter.outbound.tourism_api import fetch_congestion_trend
from src.core.logging import logger

router = APIRouter(prefix="/places", tags=["places"])


@router.get("/{place_id}")
async def place_detail(place_id: int):
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

    return place
