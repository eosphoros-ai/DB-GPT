from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic, Any

T = TypeVar("T")


class Result(Generic[T], BaseModel):
    success: bool
    err_code: str = None
    err_msg: str = None
    data: T = None

    @classmethod
    def succ(cls, data: T):
        return Result(success=True, err_code=None, err_msg=None, data=data)

    @classmethod
    def faild(cls, msg):
        return Result(success=False, err_code="E000X", err_msg=msg, data=None)

    @classmethod
    def faild(cls, code, msg):
        return Result(success=False, err_code=code, err_msg=msg, data=None)


class ChatSceneVo(BaseModel):
    chat_scene: str = Field(..., description="chat_scene")
    scene_name: str = Field(..., description="chat_scene name show for user")
    scene_describe: str = Field("", description="chat_scene describe ")
    param_title: str = Field("", description="chat_scene required parameter title")


class ConversationVo(BaseModel):
    """
    dialogue_uid
    """

    conv_uid: str = ""
    """ 
    user input 
    """
    user_input: str = ""
    """
    user
    """
    user_name: str = ""
    """ 
    the scene of chat 
    """
    chat_mode: str = ""

    """
    chat scene select param 
    """
    select_param: str = None


class MessageVo(BaseModel):
    """
    role that sends out the current message
    """

    role: str
    """
    current message 
    """
    context: str

    """ message postion order """
    order: int

    """
    time the current message was sent 
    """
    time_stamp: Any = None
