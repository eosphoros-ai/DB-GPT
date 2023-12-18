# Define your Pydantic schemas here
from typing import Optional
from dbgpt._private.pydantic import BaseModel, Field


class ServeRequest(BaseModel):
    """Prompt request model"""

    chat_scene: Optional[str] = None
    """
    The chat scene, e.g. chat_with_db_execute, chat_excel, chat_with_db_qa.
    """

    sub_chat_scene: Optional[str] = None
    """
    The sub chat scene.
    """

    prompt_type: Optional[str] = None
    """
    The prompt type, either common or private.
    """

    content: Optional[str] = None
    """
    The prompt content.
    """

    user_name: Optional[str] = None
    """
    The user name.
    """

    sys_code: Optional[str] = None
    """
    System code
    """

    prompt_name: Optional[str] = None
    """
    The prompt name.
    """


class ServerResponse(BaseModel):
    """Prompt response model"""

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

    sys_code: Optional[str] = None
    """
    System code
    """

    """prompt_name: prompt name"""
    prompt_name: str = None
    gmt_created: str = None
    gmt_modified: str = None
