import os
import time
import uuid
from typing import Any

from src.core.redis import get_redis_client


def check_redis_connection(client: Any | None = None) -> dict:
    """PING과 임시 키 SET/GET/DELETE로 실제 읽기·쓰기를 검증한다."""
    redis_client = client or get_redis_client()
    test_key = f"health:redis:{uuid.uuid4().hex}"
    test_value = uuid.uuid4().hex
    started_at = time.perf_counter()

    try:
        ping_ok = bool(redis_client.ping())
        redis_client.set(test_key, test_value, ex=30)
        read_ok = redis_client.get(test_key) == test_value
        redis_client.delete(test_key)
        deleted_ok = redis_client.get(test_key) is None
        info = redis_client.info("server")
    finally:
        pass

    return {
        "status": "connected" if ping_ok and read_ok and deleted_ok else "degraded",
        "type": "Redis",
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "version": info.get("redis_version", "unknown"),
        "checks": {
            "ping": ping_ok,
            "write_read": read_ok,
            "delete": deleted_ok,
        },
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
