from typing import Optional

from fastapi import Header, HTTPException

from src.application.session import decode_session_token


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다")
    try:
        return decode_session_token(authorization.removeprefix("Bearer "))
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
