import os
import json
from typing import Optional
from urllib.parse import unquote

import httpx
import redis as redis_lib

TOUR_API_BASE = "http://apis.data.go.kr/B551011/KorService2"
CACHE_TTL = 3600  # 1시간


def _get_service_key() -> str:
    # data.go.kr에서 발급된 키는 URL 인코딩된 상태로 제공되므로 디코딩 후 httpx에 위임
    return unquote(os.getenv("TOUR_API_KEY", ""))


def _redis_client() -> redis_lib.Redis:
    return redis_lib.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        username=os.getenv("REDIS_USERNAME", "oneulro"),
        password=os.getenv("REDIS_PASSWORD", ""),
        decode_responses=True,
        socket_connect_timeout=2,
    )


def _cache_get(key: str) -> Optional[list]:
    try:
        raw = _redis_client().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: list) -> None:
    try:
        _redis_client().setex(key, CACHE_TTL, json.dumps(value, ensure_ascii=False))
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
        "arrange": "Q",  # 추천순
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
        }
        for item in item_list
    ]

    _cache_set(cache_key, result)
    return result
