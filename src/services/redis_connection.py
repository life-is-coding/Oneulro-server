import os
import time
import uuid
from typing import Any

import redis


def create_redis_client() -> redis.Redis:
    """Cloud Memorystore 무인증 구성과 Redis ACL 구성을 모두 지원한다."""
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        username=os.getenv("REDIS_USERNAME") or None,
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def check_redis_connection(client: Any | None = None) -> dict:
    """PING과 임시 키 SET/GET/DELETE로 실제 읽기·쓰기를 검증한다."""
    redis_client = client or create_redis_client()
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
        # 중간 단계에서 실패해도 TTL이 30초라 임시 키가 자동 제거된다.
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
