from typing import List

from dbgpt._private.pydantic import BaseModel
from typing import Optional
from dbgpt._private.pydantic import BaseModel


class PromptManageRequest(BaseModel):
    """Model for managing prompts."""

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
