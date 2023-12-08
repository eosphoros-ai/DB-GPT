from typing import List
from dbgpt._private.pydantic import BaseModel


class PromptQueryResponse(BaseModel):
    id: int = None
    """chat_scene: for example: chat_with_db_execute, chat_excel, chat_with_db_qa"""

    chat_scene: str = None

    """sub_chat_scene: sub chat scene"""
    sub_chat_scene: str = None

    """prompt_type: common or private"""
    prompt_type: str = None

    """content: prompt content"""
    content: str = None

    """user_name: user name"""
    user_name: str = None

    """prompt_name: prompt name"""
    prompt_name: str = None
    gmt_created: str = None
    gmt_modified: str = None
