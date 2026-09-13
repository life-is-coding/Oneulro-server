from typing import Optional

from fastapi import APIRouter, Depends

from src.adapter.outbound.notification_repo import (
    count_unread_notifications,
    delete_all_notifications,
    delete_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from src.core.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def notifications(notification_type: Optional[str] = None, user=Depends(get_current_user)):
    return list_notifications(int(user["sub"]), notification_type)


@router.get("/unread-count")
def unread_count(user=Depends(get_current_user)):
    return {"unread_count": count_unread_notifications(int(user["sub"]))}


@router.patch("/read-all")
def read_all(user=Depends(get_current_user)):
    return {"updated_count": mark_all_notifications_read(int(user["sub"]))}


@router.patch("/{notification_id}/read")
def read_one(notification_id: int, user=Depends(get_current_user)):
    return mark_notification_read(int(user["sub"]), notification_id)


@router.delete("")
def delete_all(user=Depends(get_current_user)):
    return {"deleted_count": delete_all_notifications(int(user["sub"]))}


@router.delete("/{notification_id}")
def delete_one(notification_id: int, user=Depends(get_current_user)):
    delete_notification(int(user["sub"]), notification_id)
    return {"message": "알림이 삭제되었습니다"}
