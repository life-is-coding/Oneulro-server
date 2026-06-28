import os
from urllib.parse import quote_plus
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import redis
from src.routers.naeilro import router as naeilro_router

app = FastAPI(title="Oneulro API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "oneulro")
DB_USER = os.getenv("DB_USER", "oneulro")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# URL encode password to handle special characters
encoded_password = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "oneulro")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USERNAME,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=5
)

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
        redis_client.ping()
        info = redis_client.info("server")
        return {
            "status": "connected",
            "type": "Redis",
            "host": REDIS_HOST,
            "version": info.get("redis_version", "unknown")
        }
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
        redis_client.ping()
        redis_status = {"status": "connected", "host": REDIS_HOST}
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
