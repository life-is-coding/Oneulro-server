import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.dependencies import get_current_user
from src.repositories.preset_repo import get_preset, upsert_preset

router = APIRouter(prefix="/search-preset", tags=["search-preset"])


class PresetRequest(BaseModel):
    name: Optional[str] = None
    departure_station: str
    travel_days: Optional[int] = None
    companion_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    pet_mode: Optional[str] = None
    theme_tags: Optional[list[str]] = None
    natural_language_memo: Optional[str] = None


@router.get("")
def get_my_preset(user=Depends(get_current_user)):
    """내 코스 조건 조회"""
    return get_preset(int(user["sub"])) or {}


@router.put("")
def save_my_preset(body: PresetRequest, user=Depends(get_current_user)):
    """코스 조건 저장/수정"""
    data = {
        "name": body.name,
        "departure_station": body.departure_station,
        "travel_days": body.travel_days,
        "companion_type": body.companion_type,
        "budget_min": body.budget_min,
        "budget_max": body.budget_max,
        "pet_mode": body.pet_mode,
        "theme_tags": json.dumps(body.theme_tags, ensure_ascii=False) if body.theme_tags else None,
        "natural_language_memo": body.natural_language_memo,
    }
    return upsert_preset(int(user["sub"]), data)
