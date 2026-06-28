import asyncio
from fastapi import APIRouter, HTTPException, Query
from src.services.tourism_api import fetch_nearby_attractions

router = APIRouter(prefix="/naeilro", tags=["naeilro"])

# 내일로로 이동 가능한 사전 정의 루트
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
    route_type: str = Query(..., description="루트 타입: 동해안 / 남해안 / 역사문화 / 전국일주"),
    days: int = Query(3, ge=2, le=5, description="여행 일수 (2~5일)"),
):
    """
    내일로 코스 추천

    - **route_type**: 동해안 / 남해안 / 역사문화 / 전국일주
    - **days**: 여행 일수 (2~5일, 기본값 3일)
    """
    if route_type not in ROUTES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 루트입니다. 가능한 루트: {', '.join(ROUTES.keys())}",
        )

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
            "attractions": attractions,
        }
        for i, (dest, attractions) in enumerate(zip(destinations, attraction_lists))
    ]

    return {
        "route_type": route_type,
        "name": route["name"],
        "description": route["description"],
        "theme": route["theme"],
        "total_days": days,
        "course": course_days,
    }
