from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.adapter.outbound.post_repo import create_post, delete_post, get_post, list_posts, update_post
from src.core.dependencies import get_current_user

router = APIRouter(prefix="/posts", tags=["posts"])


class PostRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    course_id: Optional[int] = None


@router.get("")
def posts():
    return list_posts()


@router.get("/mine")
def my_posts(user=Depends(get_current_user)):
    return list_posts(int(user["sub"]))


@router.get("/{post_id}")
def post_detail(post_id: int):
    return get_post(post_id)


@router.post("")
def add_post(body: PostRequest, user=Depends(get_current_user)):
    return create_post(int(user["sub"]), body.title.strip(), body.content.strip(), body.course_id)


@router.put("/{post_id}")
def edit_post(post_id: int, body: PostRequest, user=Depends(get_current_user)):
    return update_post(int(user["sub"]), post_id, body.title.strip(), body.content.strip(), body.course_id)


@router.delete("/{post_id}")
def remove_post(post_id: int, user=Depends(get_current_user)):
    delete_post(int(user["sub"]), post_id)
    return {"message": "게시글이 삭제되었습니다"}
