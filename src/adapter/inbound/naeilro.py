import asyncio
import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header
from src.adapter.outbound.tourism_api import fetch_nearby_attractions
from src.application.session import decode_session_token
from src.adapter.outbound.preset_repo import upsert_preset

router = APIRouter(prefix="/naeilro", tags=["naeilro"])

# 내일로로 이동 가능한 사전 정의 루트
# TODO: 추후 AI 에이전트가 route_name/구성을 동적으로 생성하도록 대체 예정.
# 그 전까지 임시 추천 로직에 쓰는 데이터이며, 이 dict 구조(name/description/theme/destinations)를
# AI 응답 스키마의 참고 규격으로 보존한다.
ROUTES: dict[str, dict] = {
    "동해안": {
        "name": "동해안 힐링 코스",
        "description": "파란 동해 바다와 함께하는 자연 힐링 여행",
        "theme": "자연",
        "destinations": [
            {"name": "강릉", "map_x": 128.8762, "map_y": 37.7519},
            {"name": "속초", "map_x": 128.5987, "map_y": 38.2070},
            {"name": "삼척", "map_x": 129.1658, "map_y": 37.4499},
        ],
    },
    "남해안": {
        "name": "남해안 낭만 코스",
        "description": "아름다운 남해 풍경과 싱싱한 해산물의 향연",
        "theme": "자연/음식",
        "destinations": [
            {"name": "부산", "map_x": 129.0756, "map_y": 35.1795},
            {"name": "통영", "map_x": 128.4167, "map_y": 34.8544},
            {"name": "여수", "map_x": 127.6626, "map_y": 34.7604},
        ],
    },
    "서해안": {
        "name": "서해안 힐링 코스",
        "description": "노을 지는 갯벌과 해안선을 따라가는 조용한 힐링 여행",
        "theme": "자연",
        "destinations": [
            {"name": "인천", "map_x": 126.6202, "map_y": 37.4646},
            {"name": "보령", "map_x": 126.6146, "map_y": 36.3427},
            {"name": "군산", "map_x": 126.6963, "map_y": 35.9722},
            {"name": "목포", "map_x": 126.3849, "map_y": 34.7936},
        ],
    },
    "역사문화": {
        "name": "역사문화 탐방 코스",
        "description": "천년 역사의 도시들을 기차로 잇는 문화 여행",
        "theme": "문화/역사",
        "destinations": [
            {"name": "경주", "map_x": 129.2314, "map_y": 35.8562},
            {"name": "안동", "map_x": 128.7294, "map_y": 36.5684},
            {"name": "전주", "map_x": 127.1530, "map_y": 35.8242},
        ],
    },
    "전국일주": {
        "name": "전국일주 코스",
        "description": "기차로 떠나는 대한민국 대장정",
        "theme": "종합",
        "destinations": [
            {"name": "부산", "map_x": 129.0756, "map_y": 35.1795},
            {"name": "경주", "map_x": 129.2314, "map_y": 35.8562},
            {"name": "전주", "map_x": 127.1530, "map_y": 35.8242},
            {"name": "강릉", "map_x": 128.8762, "map_y": 37.7519},
            {"name": "대전", "map_x": 127.3845, "map_y": 36.3504},
        ],
    },
}


def _infer_route_from_memo(memo: Optional[str]) -> Optional[str]:
    """자유 텍스트에 루트 소속 도시명이 직접 언급되면 그 루트를 우선시킨다.
    (예: "부산에서 출발해서 휴양하는 코스" → 테마상 동해안이더라도 부산이 있는 루트로 보정)
    """
    if not memo:
        return None
    for route_key, route in ROUTES.items():
        if route_key in memo:
            return route_key
        for dest in route["destinations"]:
            if dest["name"] in memo:
                return route_key
    return None


@router.get("/routes")
async def list_routes():
    """내일로 추천 루트 목록 조회"""
    return [
        {
            "route_type": key,
            "name": val["name"],
            "description": val["description"],
            "theme": val["theme"],
            "city_count": len(val["destinations"]),
            "cities": [d["name"] for d in val["destinations"]],
        }
        for key, val in ROUTES.items()
    ]


@router.get("/courses/recommend")
async def recommend_course(
    days: int = Query(3, ge=2, le=5, description="여행 일수 (2~5일)"),
    companion_type: Optional[str] = Query(None),
    budget_range: Optional[str] = Query(None),
    pet_allowed: bool = Query(False),
    theme_tags: Optional[str] = Query(None, description="쉼표 구분 태그 예: 자연,힐링"),
    natural_language_memo: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    내일로 코스 추천

    - **days**: 여행 일수 (2~5일, 기본값 3일)
    """
    # route_type은 외부에 노출하지 않는 내부 선택값. 자유 텍스트에 지역이 언급되면 그 루트를,
    # 아니면 기본 루트를 고른다. (추후 AI 에이전트가 이 선택 로직 자체를 대체할 예정)
    route_type = _infer_route_from_memo(natural_language_memo) or "전국일주"

    # 로그인 상태면 검색 조건 자동 저장
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = decode_session_token(authorization.removeprefix("Bearer "))
            tags = [t.strip() for t in theme_tags.split(",")] if theme_tags else None
            upsert_preset(int(payload["sub"]), {
                "travel_days": days,
                "companion_type": companion_type,
                "budget_range": budget_range,
                "pet_allowed": pet_allowed,
                "theme_tags": json.dumps(tags, ensure_ascii=False) if tags else None,
                "natural_language_memo": natural_language_memo,
            })
        except Exception as e:
            print(f"[WARN] preset 자동 저장 실패: {e}")
    else:
        print(f"[WARN] preset 자동 저장 스킵: authorization 헤더 없음")

    route = ROUTES[route_type]
    destinations = route["destinations"][:days]

    try:
        # 각 목적지 관광지 정보를 병렬로 조회
        attraction_lists = await asyncio.gather(
            *[
                fetch_nearby_attractions(
                    map_x=dest["map_x"],
                    map_y=dest["map_y"],
                    radius=5000,
                    content_type_id=12,  # 관광지
                    num_of_rows=5,
                )
                for dest in destinations
            ]
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"관광공사 API 호출 실패: {str(e)}")

    course_days = [
        {
            "day": i + 1,
            "city": dest["name"],
            "lat": dest["map_y"],
            "lng": dest["map_x"],
            "attractions": attractions,
        }
        for i, (dest, attractions) in enumerate(zip(destinations, attraction_lists))
    ]

    return {
        "name": route["name"],
        "description": route["description"],
        "theme": route["theme"],
        "total_days": days,
        "course": course_days,
    }
