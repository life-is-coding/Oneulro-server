import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.core.dependencies import get_current_user
from src.adapter.outbound.preset_repo import get_preset, upsert_preset

router = APIRouter(prefix="/search-preset", tags=["search-preset"])


class PresetRequest(BaseModel):
    departure_station: Optional[str] = None
    travel_days: Optional[int] = None
    companion_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    pet_mode: Optional[str] = None
    # Backward-compatible inputs from the current client screens.
    budget_range: Optional[str] = None
    pet_allowed: bool = False
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
        "departure_station": body.departure_station,
        "travel_days": body.travel_days,
        "companion_type": body.companion_type,
        "budget_min": body.budget_min,
        "budget_max": body.budget_max,
        "pet_mode": body.pet_mode,
        "budget_range": body.budget_range,
        "pet_allowed": body.pet_allowed,
        "theme_tags": json.dumps(body.theme_tags) if body.theme_tags else None,
        "natural_language_memo": body.natural_language_memo,
    }
    return upsert_preset(int(user["sub"]), data)
