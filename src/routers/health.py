from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import get_settings
from src.core.redis import get_redis_client
from src.db import engine
from src.services.redis_connection import check_redis_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    """기본 health check"""
    return {"status": "ok"}


@router.get("/db")
async def health_db():
    """Database 연결 확인"""
    settings = get_settings()
    if engine is None:
        raise HTTPException(status_code=503, detail="Database driver not available")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {
            "status": "connected",
            "type": "PostgreSQL",
            "host": settings.DB_HOST,
            "database": settings.DB_NAME,
        }
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=503, detail=f"Database connection failed: {str(e)}"
        )


@router.get("/redis")
async def health_redis():
    """Redis 연결 확인"""
    import redis as redis_lib

    try:
        return check_redis_connection(get_redis_client())
    except redis_lib.RedisError as e:
        raise HTTPException(
            status_code=503, detail=f"Redis connection failed: {str(e)}"
        )


@router.get("/all")
async def health_all():
    """모든 서비스 연결 확인"""
    settings = get_settings()
    db_status: dict = {"status": "disconnected", "error": None}
    redis_status: dict = {"status": "disconnected", "error": None}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = {
            "status": "connected",
            "host": settings.DB_HOST,
            "database": settings.DB_NAME,
        }
    except Exception as e:
        db_status["error"] = str(e)

    try:
        redis_status = check_redis_connection(get_redis_client())
    except Exception as e:
        redis_status["error"] = str(e)

    all_healthy = (
        db_status["status"] == "connected" and redis_status["status"] == "connected"
    )

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "services": {
            "api": {"status": "connected"},
            "database": db_status,
            "redis": redis_status,
        },
    }
