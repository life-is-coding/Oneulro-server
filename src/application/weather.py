import json
import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from src.core.config import get_settings
from src.core.redis import get_redis_client

KST = ZoneInfo("Asia/Seoul")
KMA_FORECAST_URL = (
    "https://apihub.kma.go.kr/api/typ02/openApi/"
    "VilageFcstInfoService_2.0/getVilageFcst"
)
CACHE_TTL_SECONDS = 900

SKY_LABELS = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY_LABELS = {
    "0": None,
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
}


class WeatherServiceError(RuntimeError):
    pass


def lat_lng_to_grid(lat: float, lng: float) -> tuple[int, int]:
    """기상청 동네예보 Lambert Conformal Conic 격자 변환."""
    re = 6371.00877 / 5.0
    slat1 = math.radians(30.0)
    slat2 = math.radians(60.0)
    olon = math.radians(126.0)
    olat = math.radians(38.0)
    xo, yo = 43.0, 136.0

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5)
        / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = (
        math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn
        * math.cos(slat1)
        / sn
    )
    ro = re * sf / (math.tan(math.pi * 0.25 + olat * 0.5) ** sn)
    ra = re * sf / (math.tan(math.pi * 0.25 + math.radians(lat) * 0.5) ** sn)
    theta = math.radians(lng) - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    return int(ra * math.sin(theta) + xo + 0.5), int(ro - ra * math.cos(theta) + yo + 0.5)


def latest_base_datetime(now: datetime | None = None) -> datetime:
    """발표 지연을 고려해 15분 전 기준으로 가장 최근 단기예보 발표시각을 구한다."""
    current = (now or datetime.now(KST)).astimezone(KST) - timedelta(minutes=15)
    base_hours = (2, 5, 8, 11, 14, 17, 20, 23)
    candidates = [current.replace(hour=h, minute=0, second=0, microsecond=0) for h in base_hours]
    available = [candidate for candidate in candidates if candidate <= current]
    if available:
        return max(available)
    yesterday = current - timedelta(days=1)
    return yesterday.replace(hour=23, minute=0, second=0, microsecond=0)


def _cache_get(key: str) -> dict[str, Any] | None:
    try:
        raw = get_redis_client().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: dict[str, Any]) -> None:
    try:
        get_redis_client().setex(key, CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


def _normalize(items: list[dict[str, Any]], base: datetime) -> dict[str, Any]:
    grouped: dict[str, dict[str, str]] = {}
    for item in items:
        forecast_at = f"{item['fcstDate']}{item['fcstTime']}"
        grouped.setdefault(forecast_at, {})[item["category"]] = str(item["fcstValue"])

    now_key = datetime.now(KST).strftime("%Y%m%d%H%M")
    future_keys = sorted(key for key in grouped if key >= now_key)
    selected_key = future_keys[0] if future_keys else max(grouped, default=None)
    if selected_key is None:
        raise WeatherServiceError("기상청 예보 데이터가 비어 있습니다")

    values = grouped[selected_key]
    precipitation = PTY_LABELS.get(values.get("PTY", "0"))
    summary = precipitation or SKY_LABELS.get(values.get("SKY", ""), "알 수 없음")
    return {
        "forecast_at": datetime.strptime(selected_key, "%Y%m%d%H%M").replace(tzinfo=KST).isoformat(),
        "base_at": base.isoformat(),
        "temperature": float(values["TMP"]) if "TMP" in values else None,
        "humidity": int(float(values["REH"])) if "REH" in values else None,
        "precipitation_probability": int(float(values["POP"])) if "POP" in values else None,
        "wind_speed": float(values["WSD"]) if "WSD" in values else None,
        "sky": SKY_LABELS.get(values.get("SKY", "")),
        "precipitation_type": precipitation,
        "summary": summary,
    }


async def fetch_weather(lat: float, lng: float) -> dict[str, Any]:
    auth_key = get_settings().KMA_API_KEY.strip()
    if not auth_key:
        raise WeatherServiceError("KMA_API_KEY 환경변수가 설정되지 않았습니다")

    nx, ny = lat_lng_to_grid(lat, lng)
    base = latest_base_datetime()
    cache_key = f"weather:kma:{nx}:{ny}:{base:%Y%m%d%H}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    params = {
        "pageNo": 1,
        "numOfRows": 1000,
        "dataType": "JSON",
        "base_date": base.strftime("%Y%m%d"),
        "base_time": base.strftime("%H%M"),
        "nx": nx,
        "ny": ny,
        "authKey": auth_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(KMA_FORECAST_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise WeatherServiceError(
            f"기상청 API 호출 실패 (HTTP {exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise WeatherServiceError("기상청 API 연결에 실패했습니다") from exc
    except ValueError as exc:
        raise WeatherServiceError("기상청 API 응답을 해석할 수 없습니다") from exc

    header = payload.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        raise WeatherServiceError(
            f"기상청 API 오류: {header.get('resultCode')} - {header.get('resultMsg')}"
        )
    items = payload.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    result = {
        "coordinates": {"lat": lat, "lng": lng, "nx": nx, "ny": ny},
        "current": _normalize(items, base),
        "source": "기상청 API허브 단기예보",
        "cached": False,
    }
    _cache_set(cache_key, result)
    return result
