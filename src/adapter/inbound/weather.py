from fastapi import APIRouter, Depends, HTTPException

from src.core.dependencies import get_current_user
import asyncio

from src.adapter.outbound.weather_repo import (
    get_course_weather_destination,
    get_home_weather_destinations,
)
from src.application.weather import WeatherServiceError, fetch_weather


router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/home")
async def home_weather():
    """메인 화면에 노출할 5개 샘플 역 날씨."""
    destinations = get_home_weather_destinations()

    async def with_weather(destination: dict):
        try:
            weather = await fetch_weather(float(destination["lat"]), float(destination["lng"]))
            return {"destination": destination, "weather": weather, "weather_error": None}
        except WeatherServiceError:
            return {
                "destination": destination,
                "weather": None,
                "weather_error": "날씨 정보를 불러오지 못했어요",
            }

    return await asyncio.gather(*(with_weather(destination) for destination in destinations))


@router.get("/courses/{course_id}")
async def course_weather(course_id: int, user=Depends(get_current_user)):
    """코스의 첫 번째 목적지 단기예보 조회."""
    destination = get_course_weather_destination(course_id, int(user["sub"]))
    if not destination:
        raise HTTPException(
            status_code=404,
            detail="코스를 찾을 수 없거나 목적지 좌표가 없습니다",
        )
    try:
        weather = await fetch_weather(float(destination["lat"]), float(destination["lng"]))
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"destination": destination, "weather": weather}
