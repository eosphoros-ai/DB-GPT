import json

from fastapi import Header
from pydantic import BaseModel


class UserRequest(BaseModel):
    user_id: str = None
    user_no: str = None
    user_name: str = None # 同user_id
    user_channel: str = None
    role: str = "normal"
    nick_name: str = None
    email: str = None
    avatar_url: str = None


def get_user_from_headers(user_id: str = Header(...)):
    try:
        return UserRequest(user_id=user_id)
    except Exception as e:
        raise f"Authentication failed."
