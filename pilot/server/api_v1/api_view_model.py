from pydantic import BaseModel, Field
from typing import TypeVar, Union, List, Generic

T = TypeVar('T')


class Result(Generic[T], BaseModel):
    success: bool
    err_code: str
    err_msg: str
    data: List[T]

    @classmethod
    def succ(cls, data: List[T]):
        return Result(True, None, None, data)

    @classmethod
    def faild(cls, msg):
        return Result(True, "E000X", msg, None)

    @classmethod
    def faild(cls, code, msg):
        return Result(True, code, msg, None)


class ConversationVo(BaseModel):
    """
    dialogue_uid
    """
    conv_uid: str = Field(...,  description="dialogue uid")
    """ 
    user input 
    """
    user_input: str
    """ 
    the scene of chat 
    """
    chat_mode: str  = Field(..., description="the scene of chat ")
    """
    chat scene select param 
    """
    select_param: str


class MessageVo(BaseModel):
    """
    role that sends out the current message 
    """
    role: str
    """
    current message 
    """
    context: str
    """
    time the current message was sent 
    """
    time_stamp: float
