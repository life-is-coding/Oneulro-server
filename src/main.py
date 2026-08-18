from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.logging import RequestLoggingMiddleware
from src.core.redis import close_redis_client, get_redis_client
from src.adapter.inbound import auth, courses, naeilro, places, search_preset, users, weather
from src.adapter.inbound.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_redis_client()
    yield
    close_redis_client()


app = FastAPI(title="Oneulro API", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/")
async def root():
    return {"message": "Oneulro API - Deployment Test", "version": "0.1.0"}


# 라우터 등록
app.include_router(health_router        , prefix="/api")    # /api/health/**        상태 점검
app.include_router(auth.router          , prefix="/api")    # /api/auth/**          인증 (카카오 OAuth)
app.include_router(users.router         , prefix="/api")    # /api/users/**         사용자 프로필
app.include_router(courses.router       , prefix="/api")    # /api/courses/**       여행 코스
app.include_router(places.router        , prefix="/api")    # /api/places/**        장소 상세
app.include_router(naeilro.router       , prefix="/api")    # /api/naeilro/**       내일로 추천
app.include_router(search_preset.router , prefix="/api")    # /api/search-preset/** 검색 프리셋
app.include_router(weather.router       , prefix="/api")    # /api/weather/**       날씨 조회
