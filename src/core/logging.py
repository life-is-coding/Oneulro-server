import logging
import sys
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import get_settings


def setup_logging() -> logging.Logger:
    """애플리케이션 로거 초기화. Cloud Run 환경에서는 stdout이 Cloud Logging으로 수집된다."""
    logger = logging.getLogger("oneulro")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, get_settings().LOG_LEVEL))
    return logger


logger = setup_logging()

# health check 경로는 로그 생략
_SKIP_PATHS = {"/api/health", "/api/health/db", "/api/health/redis", "/api/health/all"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        msg = "%s %s %d %sms"
        args = (request.method, request.url.path, response.status_code, elapsed_ms)

        # 5xx → ERROR, 4xx → WARNING, 나머지 → DEBUG
        if response.status_code >= 500:
            logger.error(msg, *args)
        elif response.status_code >= 400:
            logger.warning(msg, *args)
        else:
            logger.debug(msg, *args)

        return response
