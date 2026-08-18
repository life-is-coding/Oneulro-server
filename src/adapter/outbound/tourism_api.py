import json
from urllib.parse import unquote

import httpx

from src.core.config import get_settings
from src.core.redis import get_redis_client

TOUR_API_BASE = "http://apis.data.go.kr/B551011/KorService2"
CNCTR_API_BASE = "http://apis.data.go.kr/B551011/TatsCnctrRateService"
CACHE_TTL = 3600  # 1시간
CNCTR_CACHE_TTL = 6 * 3600  # 6시간 (일 단위 예측 데이터라 자주 안 바뀜)


def _get_service_key() -> str:
    return unquote(get_settings().TOUR_API_KEY)


def _cache_get(key: str) -> list | None:
    try:
        raw = get_redis_client().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: list) -> None:
    try:
        get_redis_client().setex(key, CACHE_TTL, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


async def fetch_nearby_attractions(
    map_x: float,
    map_y: float,
    radius: int = 5000,
    content_type_id: int = 12,
    num_of_rows: int = 5,
) -> list[dict]:
    cache_key = f"tour:location:{map_x}:{map_y}:{radius}:{content_type_id}:{num_of_rows}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    service_key = _get_service_key()
    if not service_key:
        return []

    params = {
        "serviceKey": service_key,
        "numOfRows": num_of_rows,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "Oneulro",
        "_type": "json",
        "mapX": map_x,
        "mapY": map_y,
        "radius": radius,
        "contentTypeId": content_type_id,
        "arrange": "Q",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{TOUR_API_BASE}/locationBasedList2", params=params)
        resp.raise_for_status()
        data = resp.json()

    result_code = data.get("response", {}).get("header", {}).get("resultCode", "")
    if result_code != "0000":
        result_msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
        raise RuntimeError(f"관광공사 API 오류: {result_code} - {result_msg}")

    items = data.get("response", {}).get("body", {}).get("items") or {}
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    result = [
        {
            "contentid": item.get("contentid"),
            "title": item.get("title"),
            "addr": item.get("addr1"),
            "image": item.get("firstimage"),
            "mapx": item.get("mapx"),
            "mapy": item.get("mapy"),
            # 관광지 집중률(혼잡도) API 조회용 법정동 지역코드. 항목에 없으면 None.
            "area_cd": item.get("lDongRegnCd") or None,
            "signgu_cd": (
                f"{item['lDongRegnCd']}{item['lDongSignguCd']}"
                if item.get("lDongRegnCd") and item.get("lDongSignguCd")
                else None
            ),
        }
        for item in item_list
    ]

    _cache_set(cache_key, result)
    return result


async def fetch_congestion_trend(area_cd: str, signgu_cd: str, place_name: str) -> list[dict]:
    """관광지 집중률(방문자 추이) 조회. 해당 관광지가 큐레이션 대상이 아니면 빈 리스트를 반환한다."""
    cache_key = f"tour:cnctr:{area_cd}:{signgu_cd}:{place_name}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    service_key = _get_service_key()
    if not service_key or not area_cd or not signgu_cd:
        return []

    params = {
        "serviceKey": service_key,
        "numOfRows": 30,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "Oneulro",
        "_type": "json",
        "areaCd": area_cd,
        "signguCd": signgu_cd,
        "tAtsNm": place_name,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{CNCTR_API_BASE}/tatsCnctrRatedList", params=params)
        resp.raise_for_status()
        data = resp.json()

    result_code = data.get("response", {}).get("header", {}).get("resultCode", "")
    if result_code != "0000":
        result_msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
        raise RuntimeError(f"관광공사 집중률 API 오류: {result_code} - {result_msg}")

    items = data.get("response", {}).get("body", {}).get("items") or {}
    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    result = [
        {"date": item.get("baseYmd"), "rate": float(item["cnctrRate"])}
        for item in item_list
        if item.get("cnctrRate") is not None
    ]

    _cache_set(cache_key, result)
    return result
