from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "postgres"
    DB_NAME: str = "oneulro"
    DB_USER: str = "oneulro"
    DB_PASSWORD: str = ""
    DB_PORT: str = "5432"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USERNAME: str = ""
    REDIS_PASSWORD: str = ""

    # JWT
    JWT_SECRET: str = ""

    # Session
    SESSION_COOKIE_NAME: str = "oneulro_session"
    SESSION_TTL_SECONDS: int = 60 * 60 * 24 * 30
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_SECURE: bool = False

    # Kakao OAuth
    KAKAO_REST_API_KEY: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = ""

    # Naver OAuth
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    NAVER_REDIRECT_URI: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # 기상청 API
    KMA_API_KEY: str = ""

    # 관광공사 API (URL-encoded 상태로 제공됨)
    TOUR_API_KEY: str = ""

    # Logging (DEBUG / INFO / WARNING / ERROR)
    LOG_LEVEL: str = "WARNING"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
