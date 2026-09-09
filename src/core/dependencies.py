from fastapi import Request

from src.application.session import get_redis_session
from src.core.config import get_settings


def get_current_user(request: Request) -> dict:
    cookie_name = get_settings().SESSION_COOKIE_NAME
    return get_redis_session(request.cookies.get(cookie_name))
