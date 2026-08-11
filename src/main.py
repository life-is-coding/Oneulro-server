import os
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from src.db import engine, DB_HOST, DB_NAME
from src.services.redis_connection import check_redis_connection, create_redis_client
import redis
from src.routers.naeilro import router as naeilro_router
from src.routers.auth import router as auth_router
from src.routers.users import router as users_router
from src.routers.courses import router as courses_router
from src.routers.search_preset import router as search_preset_router
from src.routers.weather import router as weather_router

app = FastAPI(title="Oneulro API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
redis_client = create_redis_client()

# API Router with /api prefix
api_router = APIRouter(prefix="/api")

@api_router.get("/")
async def root():
    return {"message": "Oneulro API - Deployment Test", "version": "0.1.0"}

@api_router.get("/health")
async def health():
    """기본 health check"""
    return {"status": "ok"}

@api_router.get("/health/db")
async def health_db():
    """Database 연결 확인"""
    if engine is None:
        raise HTTPException(status_code=503, detail="Database driver not available")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {
            "status": "connected",
            "type": "PostgreSQL",
            "host": DB_HOST,
            "database": DB_NAME
        }
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")

@api_router.get("/health/redis")
async def health_redis():
    """Redis 연결 확인"""
    try:
        return check_redis_connection(redis_client)
    except redis.RedisError as e:
        raise HTTPException(status_code=503, detail=f"Redis connection failed: {str(e)}")

@api_router.get("/health/all")
async def health_all():
    """모든 서비스 연결 확인"""
    db_status = {"status": "disconnected", "error": None}
    redis_status = {"status": "disconnected", "error": None}

    # DB 체크
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = {"status": "connected", "host": DB_HOST, "database": DB_NAME}
    except Exception as e:
        db_status["error"] = str(e)

    # Redis 체크
    try:
        redis_status = check_redis_connection(redis_client)
    except Exception as e:
        redis_status["error"] = str(e)

    all_healthy = db_status["status"] == "connected" and redis_status["status"] == "connected"

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "services": {
            "api": {"status": "connected"},
            "database": db_status,
            "redis": redis_status
        }
    }

app.include_router(api_router)
app.include_router(naeilro_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(courses_router, prefix="/api")
app.include_router(search_preset_router, prefix="/api")
app.include_router(weather_router, prefix="/api")
