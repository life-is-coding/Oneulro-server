"""Cloud Run 컨테이너의 REDIS_* 환경변수로 Redis 연결을 점검한다."""

import json

from src.services.redis_connection import check_redis_connection


if __name__ == "__main__":
    print(json.dumps(check_redis_connection(), ensure_ascii=False, indent=2))
